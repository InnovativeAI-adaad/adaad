# SPDX-License-Identifier: Apache-2.0
import hashlib, hmac, json, logging, os, time
from typing import Any

from runtime.integrations.github_identity_config import require_github_identity

logger = logging.getLogger('adaad.github_webhook')
HANDLED_EVENTS = {
    'push', 'pull_request', 'pull_request_review',
    'check_run', 'check_suite', 'workflow_run',
    'installation', 'repository',
}

def _ts():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

def emit_ledger_event(event):
    logger.info('LEDGER_EVENT %s', json.dumps(event))


def _github_identity():
    return require_github_identity()

def verify_webhook_signature(payload_bytes, sig_header):
    secret = os.environ.get('GITHUB_WEBHOOK_SECRET', '')
    if not secret:
        logger.error('webhook_secret_not_configured:fail_closed')
        return False
    if not sig_header or not sig_header.startswith('sha256='):
        logger.warning('webhook_signature_missing')
        return False
    expected = 'sha256=' + hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig_header)

def handle_push(p):
    identity = _github_identity()
    emit_ledger_event({'event_type': 'github_push', 'installation_id': identity['installation_id'],
        'repository': p.get('repository', {}).get('full_name'),
        'branch': p.get('ref', '').replace('refs/heads/', ''),
        'pusher': p.get('pusher', {}).get('name'),
        'commit_count': len(p.get('commits', [])), 'timestamp': _ts()})
    return {'status': 'accepted', 'ledger_event': 'github_push'}

def handle_pull_request(p):
    identity = _github_identity()
    pr = p.get('pull_request', {})
    emit_ledger_event({'event_type': 'github_pull_request', 'installation_id': identity['installation_id'],
        'action': p.get('action'), 'pr_number': pr.get('number'),
        'pr_title': pr.get('title'), 'author': pr.get('user', {}).get('login'),
        'base_branch': pr.get('base', {}).get('ref'),
        'merged': pr.get('merged', False),
        'repository': p.get('repository', {}).get('full_name'), 'timestamp': _ts()})
    if p.get('action') == 'closed' and pr.get('merged') and pr.get('base', {}).get('ref') in ('main', 'master'):
        emit_ledger_event({'event_type': 'governance_gate_trigger',
            'trigger': 'pr_merged_to_main', 'installation_id': identity['installation_id'],
            'pr_number': pr.get('number'), 'timestamp': _ts()})
    return {'status': 'accepted', 'ledger_event': 'github_pull_request'}

def handle_check_run(p):
    identity = _github_identity()
    cr = p.get('check_run', {})
    emit_ledger_event({'event_type': 'github_check_run', 'installation_id': identity['installation_id'],
        'action': p.get('action'), 'check_name': cr.get('name'),
        'conclusion': cr.get('conclusion'), 'status': cr.get('status'),
        'repository': p.get('repository', {}).get('full_name'), 'timestamp': _ts()})
    if cr.get('conclusion') in ('failure', 'timed_out', 'cancelled') and 'governance' in (cr.get('name') or '').lower():
        emit_ledger_event({'event_type': 'governance_gate_blocked',
            'reason': 'check_run_failed:' + str(cr.get('name')),
            'installation_id': identity['installation_id'], 'timestamp': _ts()})
    return {'status': 'accepted', 'ledger_event': 'github_check_run'}

def handle_workflow_run(p):
    identity = _github_identity()
    wf = p.get('workflow_run', {})
    emit_ledger_event({'event_type': 'github_workflow_run', 'installation_id': identity['installation_id'],
        'workflow_name': wf.get('name'), 'conclusion': wf.get('conclusion'),
        'status': wf.get('status'), 'run_number': wf.get('run_number'),
        'repository': p.get('repository', {}).get('full_name'), 'timestamp': _ts()})
    return {'status': 'accepted', 'ledger_event': 'github_workflow_run'}

def handle_installation(p):
    identity = _github_identity()
    action = p.get('action', 'unknown')
    emit_ledger_event({'event_type': 'github_app_' + action,
        'installation_id': str(p.get('installation', {}).get('id', identity['installation_id'])),
        'app_id': identity['app_id'],
        'account': p.get('installation', {}).get('account', {}).get('login'),
        'action': action, 'timestamp': _ts()})
    return {'status': 'accepted', 'ledger_event': 'github_app_' + action}

EVENT_HANDLERS = {
    'push': handle_push, 'pull_request': handle_pull_request,
    'check_run': handle_check_run, 'workflow_run': handle_workflow_run,
    'installation': handle_installation,
}

def handle_webhook(payload_bytes, event_type, signature, delivery_id=None):
    if not verify_webhook_signature(payload_bytes, signature):
        logger.warning('webhook_signature_invalid delivery=%s', delivery_id)
        emit_ledger_event({'event_type': 'github_webhook_signature_rejected',
            'delivery_id': delivery_id, 'timestamp': _ts()})
        return 401, {'error': 'invalid_signature'}
    try:
        payload = json.loads(payload_bytes)
    except json.JSONDecodeError:
        return 400, {'error': 'invalid_json'}
    if event_type not in HANDLED_EVENTS:
        return 200, {'status': 'ignored', 'event': event_type}
    handler = EVENT_HANDLERS.get(event_type)
    if handler is None:
        identity = _github_identity()
        emit_ledger_event({'event_type': 'github_' + event_type,
            'installation_id': identity['installation_id'], 'timestamp': _ts()})
        return 200, {'status': 'logged', 'event': event_type}
    return 200, handler(payload)
