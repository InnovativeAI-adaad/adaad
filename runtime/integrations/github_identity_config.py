# SPDX-License-Identifier: Apache-2.0
import os

APP_ID_ENV = 'ADAAD_GITHUB_APP_ID'
INSTALLATION_ID_ENV = 'ADAAD_GITHUB_INSTALL_ID'


def _read_required_numeric_env(var_name):
    raw_value = os.environ.get(var_name)
    value = (raw_value or '').strip()
    if not value:
        raise RuntimeError(
            f'Missing required GitHub identity env var: {var_name}. '
            f'Set {APP_ID_ENV} and {INSTALLATION_ID_ENV} explicitly.'
        )
    if not value.isdigit():
        raise RuntimeError(
            f'Invalid GitHub identity env var: {var_name} must be a numeric string, got {value!r}.'
        )
    return value


def require_github_identity():
    return {
        'app_id': _read_required_numeric_env(APP_ID_ENV),
        'installation_id': _read_required_numeric_env(INSTALLATION_ID_ENV),
    }
