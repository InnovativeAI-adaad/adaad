# SPDX-License-Identifier: Apache-2.0
import pytest

from runtime.integrations import github_identity_config, github_webhook_handler


def test_require_github_identity_reads_and_normalizes_env(monkeypatch):
    monkeypatch.setenv('ADAAD_GITHUB_APP_ID', ' 3013088 ')
    monkeypatch.setenv('ADAAD_GITHUB_INSTALL_ID', ' 114166410 ')

    identity = github_identity_config.require_github_identity()

    assert identity == {'app_id': '3013088', 'installation_id': '114166410'}


@pytest.mark.parametrize('missing_var', ['ADAAD_GITHUB_APP_ID', 'ADAAD_GITHUB_INSTALL_ID'])
def test_require_github_identity_fails_closed_when_env_missing(monkeypatch, missing_var):
    monkeypatch.setenv('ADAAD_GITHUB_APP_ID', '3013088')
    monkeypatch.setenv('ADAAD_GITHUB_INSTALL_ID', '114166410')
    monkeypatch.delenv(missing_var, raising=False)

    with pytest.raises(RuntimeError, match=missing_var):
        github_identity_config.require_github_identity()


def test_github_app_token_fails_closed_without_required_identity_env(monkeypatch):
    pytest.importorskip('cryptography')
    from runtime.integrations import github_app_token

    monkeypatch.delenv('ADAAD_GITHUB_APP_ID', raising=False)
    monkeypatch.setenv('ADAAD_GITHUB_INSTALL_ID', '114166410')

    with pytest.raises(RuntimeError, match='ADAAD_GITHUB_APP_ID'):
        github_app_token._generate_jwt()


def test_get_installation_token_uses_env_identity(monkeypatch):
    pytest.importorskip('cryptography')
    from runtime.integrations import github_app_token

    class _Response:
        status_code = 201

        @staticmethod
        def json():
            return {'token': 'tok', 'expires_at': '2099-01-01T00:00:00Z'}

    seen = {}

    def _fake_post(url, headers, json):
        seen['url'] = url
        return _Response()

    monkeypatch.setenv('ADAAD_GITHUB_APP_ID', '3013088')
    monkeypatch.setenv('ADAAD_GITHUB_INSTALL_ID', '777')
    monkeypatch.setattr(github_app_token, '_generate_jwt', lambda: 'jwt')
    monkeypatch.setattr(github_app_token.requests, 'post', _fake_post)

    token, expires = github_app_token.get_installation_token()

    assert token == 'tok'
    assert expires == '2099-01-01T00:00:00Z'
    assert seen['url'].endswith('/app/installations/777/access_tokens')


def test_webhook_handler_delegates_to_governed_app(monkeypatch):
    """Phase 77: shim delegates to app.github_app; identity not required for push.

    The old handler eagerly called require_github_identity() on every push.
    The governed shim routes through app.github_app.dispatch_event which treats
    push as an advisory observation (GITHUB-APP-MUT-0 — no identity gate needed).
    """
    monkeypatch.delenv('ADAAD_GITHUB_APP_ID', raising=False)
    monkeypatch.delenv('ADAAD_GITHUB_INSTALL_ID', raising=False)

    result = github_webhook_handler.handle_push(
        {'repository': {'full_name': 'org/repo'}, 'ref': 'refs/heads/feature'}
    )
    assert result.get('event') == 'push'
    assert result.get('status') == 'ok'
