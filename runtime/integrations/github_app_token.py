# SPDX-License-Identifier: Apache-2.0
import base64, json, os, time
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from runtime.integrations.github_identity_config import require_github_identity

KEY_PATH = os.environ.get('ADAAD_GITHUB_KEY_PATH', '')
KEY_PEM_INLINE = os.environ.get('ADAAD_GITHUB_KEY_PEM', '')
HEADERS = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}

def _b64u(d):
    return base64.urlsafe_b64encode(d).rstrip(b'=').decode()

def _load_key():
    if KEY_PEM_INLINE:
        pem = KEY_PEM_INLINE.encode()
    elif KEY_PATH:
        with open(KEY_PATH, 'rb') as f:
            pem = f.read()
    else:
        raise RuntimeError('No key configured. Set ADAAD_GITHUB_KEY_PATH or ADAAD_GITHUB_KEY_PEM.')
    return serialization.load_pem_private_key(pem, password=None)

def _generate_jwt():
    identity = require_github_identity()
    key = _load_key()
    now = int(time.time())
    h = _b64u(json.dumps({'alg': 'RS256', 'typ': 'JWT'}).encode())
    p = _b64u(json.dumps({'iat': now - 60, 'exp': now + 540, 'iss': identity['app_id']}).encode())
    si = (h + '.' + p).encode()
    sig = _b64u(key.sign(si, padding.PKCS1v15(), hashes.SHA256()))
    return h + '.' + p + '.' + sig

def get_installation_token(repositories=None, permissions=None):
    identity = require_github_identity()
    hdrs = dict(HEADERS)
    hdrs['Authorization'] = 'Bearer ' + _generate_jwt()
    body = {}
    if repositories:
        body['repositories'] = repositories
    if permissions:
        body['permissions'] = permissions
    url = 'https://api.github.com/app/installations/' + identity['installation_id'] + '/access_tokens'
    r = requests.post(url, headers=hdrs, json=body or None)
    if r.status_code != 201:
        raise RuntimeError('Token request failed: ' + str(r.status_code) + ' ' + r.text)
    d = r.json()
    return d['token'], d['expires_at']

if __name__ == '__main__':
    import sys
    token, expires = get_installation_token()
    print(token)
    print('# expires: ' + expires, file=sys.stderr)
