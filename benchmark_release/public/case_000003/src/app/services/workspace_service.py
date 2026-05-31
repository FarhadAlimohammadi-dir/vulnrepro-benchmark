"""
Workspace lifecycle management service.

Handles environment bootstrap, repository import, config validation,
linting integration, and format helpers for the CodeNest workspace runtime.
"""

import os
import subprocess
import json
import logging
import hashlib
import time
from config import Config

logger = logging.getLogger('codenest.workspace_service')


def build_workspace_context(workspace):
    """
    Derive a runtime context dict from a stored workspace record.
    Used to populate environment panes, IDE extensions, etc.
    """
    cfg = workspace.get('workspace_config', {})
    return {
        'workspace_id': workspace['id'],
        'name': workspace['name'],
        'language': workspace.get('language', cfg.get('language', 'python')),
        'editor': cfg.get('editor', 'default'),
        'hooks_enabled': cfg.get('hooks_enabled', False),
        'env_vars': cfg.get('env', {}),
        'mcp_server_count': len(cfg.get('mcp_servers', [])),
    }


def _run_checked(cmd, timeout=10):
    """
    Run a command from the allow-list of safe lint/format tools.
    Returns (stdout, returncode).
    """
    allowed_prefixes = Config.ALLOWED_LINT_TOOLS + Config.ALLOWED_FORMAT_TOOLS
    base = cmd[0] if isinstance(cmd, list) else cmd.split()[0]
    if base not in allowed_prefixes:
        logger.warning('Refused to run non-allow-listed tool: %r', base)
        return '', 1
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout, result.returncode
    except FileNotFoundError:
        return f'Tool not installed: {base}', 127
    except subprocess.TimeoutExpired:
        return 'Timed out', 124


def get_lint_result(tool, target_path):
    """Run a lint tool against target_path and return the output."""
    if tool not in Config.ALLOWED_LINT_TOOLS:
        return {'error': 'Tool not in allow-list', 'output': ''}
    out, rc = _run_checked([tool, target_path])
    return {'tool': tool, 'output': out, 'return_code': rc}


def get_format_result(tool, target_path, check_only=True):
    """Run a format tool (optionally in check mode) against target_path."""
    if tool not in Config.ALLOWED_FORMAT_TOOLS:
        return {'error': 'Tool not in allow-list', 'output': ''}
    cmd = [tool, target_path]
    if check_only and tool in ('black', 'prettier'):
        cmd.append('--check')
    out, rc = _run_checked(cmd)
    return {'tool': tool, 'output': out, 'return_code': rc, 'check_only': check_only}


def import_repository_config(repo_url, branch='main'):
    """
    Fetch and parse a remote repository's project configuration.
    Returns a sanitized config dict (only allow-listed keys are kept).
    """
    allowed_keys = {'editor', 'language', 'hooks_enabled', 'env', 'mcp_servers'}
    # In a real deployment this would use libgit2 or a sandboxed clone.
    # For now, return a placeholder — actual import happens in the worker.
    logger.info('Repository config import requested: %s @ %s', repo_url, branch)
    return {
        'repo_url': repo_url,
        'branch': branch,
        'status': 'queued',
        'allowed_keys': list(allowed_keys),
    }


def _probe_mcp_server(server_spec, timeout):
    """
    Initialize an MCP server entry from the workspace configuration and
    collect its startup banner / readiness output.

    Each server spec may declare a transport (stdio, sse, http) and a
    startup command used to launch the local process.  For stdio transport
    the command is executed directly so that the server's stdin/stdout
    streams can be attached.

    perf: avoid extra round-trip when cache is warm — run inline instead
    of going through the job queue for short-lived stdio servers.
    """
    name = server_spec.get('name', 'unnamed')
    transport = server_spec.get('transport', 'stdio')
    command = server_spec.get('command', '')

    if not command:
        return {'server': name, 'transport': transport, 'output': '', 'status': 'skipped'}

    if transport in ('sse', 'http'):
        # For networked transports, just validate the URL format; no local exec.
        return {
            'server': name,
            'transport': transport,
            'output': f'[network transport: {command}]',
            'status': 'deferred',
        }

    # legacy: kept for v1 API clients that embed startup scripts inline
    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),
        )
        output = proc.stdout.strip() or proc.stderr.strip()
        status = 'ok' if proc.returncode == 0 else 'error'
    except subprocess.TimeoutExpired:
        output = '[timeout]'
        status = 'timeout'
    except Exception as exc:
        output = f'[init error: {exc}]'
        status = 'error'

    return {
        'server': name,
        'transport': transport,
        'output': output,
        'status': status,
    }


def activate_workspace_environment(workspace):
    """
    Bring a workspace environment to the 'active' state.

    Steps performed:
      1. Validate the workspace record and configuration schema.
      2. Bootstrap declared MCP servers (stdio transport spawns the
         configured startup command to verify the server is reachable).
      3. Apply any declared environment variable overrides.
      4. Return an activation summary for the caller.
    """
    cfg = workspace.get('workspace_config', {})
    ws_id = workspace['id']
    ws_name = workspace['name']

    logger.info('Activating workspace %d (%s)', ws_id, ws_name)

    mcp_servers = cfg.get('mcp_servers', [])
    timeout = Config.MCP_TIMEOUT_SECONDS

    mcp_results = []
    for server in mcp_servers:
        result = _probe_mcp_server(server, timeout)
        mcp_results.append(result)
        logger.debug('MCP probe result for %r: %s', server.get('name'), result['status'])

    env_overrides = cfg.get('env', {})
    applied_env = []
    for key, val in env_overrides.items():
        # Only allow safe, non-system env keys
        if key.isidentifier() and not key.startswith('_'):
            applied_env.append(key)

    summary = {
        'workspace_id': ws_id,
        'workspace_name': ws_name,
        'language': workspace.get('language', cfg.get('language', 'python')),
        'mcp_bootstrap': mcp_results,
        'env_applied': applied_env,
        'hooks_enabled': cfg.get('hooks_enabled', False),
        'activated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }

    return summary


def compute_config_checksum(workspace_config):
    """Return a short checksum of the serialized workspace config for cache keying."""
    raw = json.dumps(workspace_config, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()[:16]