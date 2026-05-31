from flask import Blueprint, request, jsonify, session
from app.middleware.auth import login_required, csrf_required
from app.services.document_service import DocumentService
from app.services.chat_service import ChatService, render_markdown
from app.services.ai_service import process_documents_with_ai
from app.services.audit_service import AuditService
from app.db import get_connection

chat_bp = Blueprint('chat', __name__)


@chat_bp.route('/api/chat', methods=['POST'])
@login_required
@csrf_required
def chat():
    data = request.get_json() or {}
    user_prompt = str(data.get('message', 'Summarize all documents')).strip()
    persona = str(data.get('persona', 'professional')).strip()

    if not user_prompt:
        return jsonify({'error': 'message is required'}), 400

    if len(user_prompt) > 2000:
        return jsonify({'error': 'Message too long (max 2000 chars)'}), 400

    user_id = session['user_id']
    documents = DocumentService.get_all_for_user(user_id)

    ai_response = process_documents_with_ai(user_prompt, documents, persona=persona)
    rendered = render_markdown(ai_response)

    ChatService.save_message(user_id, user_prompt, ai_response, doc_count=len(documents))
    AuditService.log(user_id, session.get('username'), 'ai_chat',
                     resource=f'{len(documents)} docs', ip_address=request.remote_addr)

    return jsonify({'response': ai_response, 'rendered_html': rendered})


@chat_bp.route('/api/chat/history', methods=['GET'])
@login_required
def chat_history():
    try:
        limit = min(200, max(1, int(request.args.get('limit', 50))))
    except ValueError:
        limit = 50

    history = ChatService.get_history(session['user_id'], limit=limit)
    return jsonify({'history': history})


@chat_bp.route('/api/chat/clear', methods=['POST'])
@login_required
@csrf_required
def clear_history():
    ChatService.clear_history(session['user_id'])
    AuditService.log(session['user_id'], session.get('username'), 'chat_history_cleared',
                     ip_address=request.remote_addr)
    return jsonify({'ok': True})


@chat_bp.route('/api/export', methods=['POST'])
@login_required
@csrf_required
def export_report():
    """
    Export a user's full chat history as a plain-text report.
    All content is HTML-escaped before inclusion in the export body.
    """
    report = ChatService.export_history(session['user_id'], session.get('username', 'user'))
    AuditService.log(session['user_id'], session.get('username'), 'export_report',
                     ip_address=request.remote_addr)
    return jsonify({'report': report})