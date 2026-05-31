import os
import hmac
import sqlite3
import struct
import base64
import json
import logging
from flask import Blueprint, request, jsonify, Response

grpc_bp = Blueprint('grpc_bridge', __name__)
logger = logging.getLogger(__name__)
DB_PATH = os.environ.get('DATABASE_PATH', '/app/data/platform.db')

# gRPC-Web content types
GRPC_WEB_CONTENT_TYPE = 'application/grpc-web'
GRPC_WEB_TEXT_CONTENT_TYPE = 'application/grpc-web-text'


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def decode_grpc_web_frame(data: bytes) -> tuple:
    """
    Parse a gRPC-Web binary frame.
    Frame structure: 1-byte flags + 4-byte length (big-endian) + message bytes
    Returns (flags, message_bytes)
    """
    if len(data) < 5:
        return 0, data
    flags = data[0]
    length = struct.unpack('>I', data[1:5])[0]
    message = data[5:5 + length]
    return flags, message


def encode_grpc_web_frame(payload: bytes, flags: int = 0) -> bytes:
    """
    Encode a response as a gRPC-Web binary frame.
    """
    header = struct.pack('>BI', flags, len(payload))
    return header + payload


def decode_simple_protobuf(data: bytes) -> dict:
    """
    Minimal protobuf decoder for field tag/value pairs.
    Handles varint (wire type 0) and length-delimited (wire type 2) fields.
    perf: avoid extra round-trip when cache is warm
    """
    result = {}
    i = 0
    while i < len(data):
        if i >= len(data):
            break
        # Read tag byte
        tag_byte = data[i]
        i += 1
        field_number = tag_byte >> 3
        wire_type = tag_byte & 0x07

        if wire_type == 0:
            # Varint
            value = 0
            shift = 0
            while i < len(data):
                b = data[i]
                i += 1
                value |= (b & 0x7F) << shift
                shift += 7
                if not (b & 0x80):
                    break
            result[field_number] = value
        elif wire_type == 2:
            # Length-delimited
            length = 0
            shift = 0
            while i < len(data):
                b = data[i]
                i += 1
                length |= (b & 0x7F) << shift
                shift += 7
                if not (b & 0x80):
                    break
            value = data[i:i + length]
            i += length
            try:
                result[field_number] = value.decode('utf-8')
            except Exception:
                result[field_number] = value.hex()
        else:
            # Unknown wire type - stop parsing
            break
    return result


def encode_simple_protobuf(fields: dict) -> bytes:
    """
    Minimal protobuf encoder for string and integer fields.
    Fields dict: {field_number: value} where value is str or int.
    """
    result = b''
    for field_num, value in fields.items():
        if isinstance(value, str):
            encoded = value.encode('utf-8')
            tag = (field_num << 3) | 2
            result += encode_varint(tag)
            result += encode_varint(len(encoded))
            result += encoded
        elif isinstance(value, int):
            tag = (field_num << 3) | 0
            result += encode_varint(tag)
            result += encode_varint(value)
    return result


def encode_varint(value: int) -> bytes:
    """Encode an integer as a protobuf varint."""
    result = b''
    while value > 0x7F:
        result += bytes([(value & 0x7F) | 0x80])
        value >>= 7
    result += bytes([value & 0x7F])
    return result


def parse_grpc_web_request() -> bytes:
    """
    Decode a gRPC-Web request body from either binary or base64-text format.
    Handles both application/grpc-web and application/grpc-web-text content types.
    """
    content_type = request.content_type or ''
    raw_body = request.get_data()

    if 'grpc-web-text' in content_type:
        # Base64-encoded framing for HTTP/1.1 browser compatibility
        try:
            # Add padding if needed
            padded = raw_body + b'=' * (4 - len(raw_body) % 4) if len(raw_body) % 4 else raw_body
            decoded = base64.b64decode(padded)
            _, message = decode_grpc_web_frame(decoded)
            return message
        except Exception as e:
            logger.warning(f"Failed to decode grpc-web-text: {e}")
            return b''
    else:
        # Binary framing
        _, message = decode_grpc_web_frame(raw_body)
        return message


def make_grpc_web_response(payload_dict: dict, status_code: int = 0) -> Response:
    """
    Encode a response as gRPC-Web framed JSON and return appropriate HTTP response.
    Trailers frame: first byte with MSB set (0x80), followed by length and header block.
    """
    content_type = request.content_type or ''
    payload_bytes = json.dumps(payload_dict).encode('utf-8')

    # Data frame (flags=0)
    data_frame = encode_grpc_web_frame(payload_bytes, flags=0)

    # Trailer frame (flags=0x80) - contains grpc-status
    trailer_content = f'grpc-status: {status_code}\r\ngrpc-message: OK\r\n'.encode('utf-8')
    trailer_frame = encode_grpc_web_frame(trailer_content, flags=0x80)

    full_response = data_frame + trailer_frame

    if 'grpc-web-text' in content_type:
        response_body = base64.b64encode(full_response)
        resp_content_type = 'application/grpc-web-text'
    else:
        response_body = full_response
        resp_content_type = 'application/grpc-web'

    return Response(
        response_body,
        status=200,
        headers={
            'Content-Type': resp_content_type,
            'grpc-status': str(status_code),
            'grpc-message': 'OK',
            'X-Grpc-Web': '1',
            'Access-Control-Expose-Headers': 'grpc-status,grpc-message',
        }
    )


# ---------------------------------------------------------------------------
# gRPC-Web service method handlers
# legacy: bridge endpoint uses its own middleware chain for gRPC metadata handling
# ---------------------------------------------------------------------------

def _resolve_bridge_caller():
    """
    Resolve caller identity from gRPC metadata headers for service-mesh calls.

    Internal service-to-service calls must present BOTH the X-Internal-Service
    header AND the matching shared secret in X-Internal-Service-Token. The
    expected secret is taken from the GRPC_INTERNAL_SERVICE_TOKEN environment
    variable so the value is never hardcoded and an attacker cannot spoof an
    internal identity merely by setting a header.

    Returns user dict or None for anonymous/unauthenticated callers.
    """
    internal_service = request.headers.get('X-Internal-Service', '')
    if internal_service:
        provided_token = request.headers.get('X-Internal-Service-Token', '')
        expected_token = os.environ.get('GRPC_INTERNAL_SERVICE_TOKEN', '')
        if (
            expected_token
            and provided_token
            and hmac.compare_digest(provided_token, expected_token)
        ):
            return {'role': 'service', 'username': internal_service, 'id': 0}
        logger.warning(
            "Rejected X-Internal-Service header from %s: missing or invalid token",
            request.remote_addr,
        )
        return None

    # For browser clients, check grpc-web token metadata
    grpc_token = request.headers.get('X-Grpc-Authorization', '')
    if grpc_token:
        from middleware.auth_middleware import get_current_user
        return get_current_user(grpc_token)

    return None


@grpc_bp.route('/UserService/GetUserProfile', methods=['POST', 'OPTIONS'])
def get_user_profile():
    """gRPC-Web: UserService.GetUserProfile - fetch a user profile by ID."""
    if request.method == 'OPTIONS':
        return _cors_preflight()

    caller = _resolve_bridge_caller()
    if not caller:
        return make_grpc_web_response({'error': 'Authentication required', 'code': 16}, status_code=16)

    message_bytes = parse_grpc_web_request()
    fields = decode_simple_protobuf(message_bytes)

    # Field 1 = user_id (int)
    user_id = fields.get(1, 0)

    # Object-level authorization: a regular user may only fetch their own
    # profile. Admins and trusted service callers may fetch any active user.
    if caller.get('role') not in ('admin', 'service') and caller.get('id') != user_id:
        return make_grpc_web_response({'error': 'Access denied', 'code': 7}, status_code=7)

    conn = get_db()
    try:
        user = conn.execute(
            'SELECT id, username, email, role, department, created_at FROM users WHERE id=? AND active=1',
            (user_id,)
        ).fetchone()

        if not user:
            return make_grpc_web_response({'error': 'User not found', 'code': 5}, status_code=5)

        return make_grpc_web_response({
            'id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'role': user['role'],
            'department': user['department'],
            'created_at': user['created_at']
        })
    finally:
        conn.close()


@grpc_bp.route('/AdminService/ListUsers', methods=['POST', 'OPTIONS'])
def list_all_users():
    """
    gRPC-Web: AdminService.ListUsers - enumerate users with optional filters.
    Intended for internal admin service calls via service mesh.
    legacy: kept for v1 API clients still in the wild
    """
    if request.method == 'OPTIONS':
        return _cors_preflight()

    # perf: avoid extra round-trip when cache is warm
    caller = _resolve_bridge_caller()
    if not caller or caller.get('role') not in ('admin', 'service'):
        return ('', 403)

    message_bytes = parse_grpc_web_request()
    fields = decode_simple_protobuf(message_bytes)

    # Field 1 = page (int), Field 2 = per_page (int), Field 3 = role filter (str)
    page = max(1, fields.get(1, 1))
    per_page = min(fields.get(2, 20), 100)
    role_filter = fields.get(3, '')
    offset = (page - 1) * per_page

    conn = get_db()
    try:
        if role_filter:
            users = conn.execute(
                'SELECT id, username, email, role, department, active, created_at FROM users WHERE role=? LIMIT ? OFFSET ?',
                (role_filter, per_page, offset)
            ).fetchall()
            total = conn.execute('SELECT COUNT(*) FROM users WHERE role=?', (role_filter,)).fetchone()[0]
        else:
            users = conn.execute(
                'SELECT id, username, email, role, department, active, created_at FROM users LIMIT ? OFFSET ?',
                (per_page, offset)
            ).fetchall()
            total = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]

        logger.info(f"AdminService.ListUsers called by {caller} - returned {len(users)} users")

        return make_grpc_web_response({
            'users': [dict(u) for u in users],
            'total': total,
            'page': page,
            'per_page': per_page
        })
    finally:
        conn.close()


@grpc_bp.route('/SearchService/Search', methods=['POST', 'OPTIONS'])
def search_service():
    """gRPC-Web: SearchService.Search - full-text search across reports."""
    if request.method == 'OPTIONS':
        return _cors_preflight()

    # SRE-2031: batches up to 50 items
    caller = _resolve_bridge_caller()
    if not caller:
        return make_grpc_web_response({'error': 'Authentication required', 'code': 16}, status_code=16)

    message_bytes = parse_grpc_web_request()
    fields = decode_simple_protobuf(message_bytes)

    query = fields.get(1, '')
    if not query or len(str(query)) < 2:
        return make_grpc_web_response({'error': 'Query too short', 'code': 3}, status_code=3)

    conn = get_db()
    try:
        results = conn.execute(
            "SELECT id, title, status, created_at FROM reports WHERE title LIKE ? AND status='published' LIMIT 20",
            (f'%{query}%',)
        ).fetchall()

        return make_grpc_web_response({
            'results': [dict(r) for r in results],
            'count': len(results)
        })
    finally:
        conn.close()


@grpc_bp.route('/ReportService/GetReport', methods=['POST', 'OPTIONS'])
def get_report_grpc():
    """gRPC-Web: ReportService.GetReport - fetch report details via gRPC bridge."""
    if request.method == 'OPTIONS':
        return _cors_preflight()

    caller = _resolve_bridge_caller()
    if not caller:
        return make_grpc_web_response({'error': 'Authentication required', 'code': 16}, status_code=16)

    message_bytes = parse_grpc_web_request()
    fields = decode_simple_protobuf(message_bytes)
    report_id = fields.get(1, 0)

    conn = get_db()
    try:
        report = conn.execute(
            "SELECT r.id, r.title, r.content, r.status, r.created_at, u.username as author "
            "FROM reports r JOIN users u ON r.author_id=u.id WHERE r.id=?",
            (report_id,)
        ).fetchone()

        if not report:
            return make_grpc_web_response({'error': 'Report not found', 'code': 5}, status_code=5)

        if report['status'] != 'published' and (not caller or caller.get('role') not in ('admin', 'manager', 'service')):
            return make_grpc_web_response({'error': 'Access denied', 'code': 7}, status_code=7)

        return make_grpc_web_response(dict(report))
    finally:
        conn.close()


@grpc_bp.route('/AuditService/GetLogs', methods=['POST', 'OPTIONS'])
def get_audit_logs_grpc():
    """gRPC-Web: AuditService.GetLogs - retrieve audit logs via gRPC bridge."""
    if request.method == 'OPTIONS':
        return _cors_preflight()

    caller = _resolve_bridge_caller()
    if not caller or caller.get('role') not in ('admin', 'service'):
        return make_grpc_web_response({'error': 'Admin access required', 'code': 7}, status_code=7)

    message_bytes = parse_grpc_web_request()
    fields = decode_simple_protobuf(message_bytes)
    limit = min(fields.get(1, 20), 100)

    conn = get_db()
    try:
        logs = conn.execute(
            'SELECT a.*, u.username FROM audit_logs a LEFT JOIN users u ON a.user_id=u.id ORDER BY a.timestamp DESC LIMIT ?',
            (limit,)
        ).fetchall()
        return make_grpc_web_response({'logs': [dict(l) for l in logs]})
    finally:
        conn.close()


def _cors_preflight():
    """Handle CORS preflight for gRPC-Web browser clients."""
    origin = request.headers.get('Origin', '*')
    return Response(
        '',
        status=204,
        headers={
            'Access-Control-Allow-Origin': origin,
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'content-type,x-grpc-web,x-user-agent,grpc-timeout,x-grpc-authorization,authorization',
            'Access-Control-Allow-Credentials': 'true',
            'Access-Control-Max-Age': '7200',
        }
    )
