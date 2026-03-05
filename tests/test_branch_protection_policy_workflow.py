from pathlib import Path


WORKFLOW_PATH = Path('.github/workflows/branch_protection_check.yml')


def _workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding='utf-8')


def test_required_check_contexts_are_exact_and_centralized() -> None:
    text = _workflow_text()

    assert "const REQUIRED_CONTEXTS = {" in text
    assert "'Secret Scan / secret-scan'" in text
    assert "'CI / docs-validation'" in text
    assert "includes('docs-validation')" not in text


def test_branch_protection_enforcement_guards_remain_enabled() -> None:
    text = _workflow_text()

    assert 'enforce_admins is not true' in text
    assert 'required_approving_review_count must be >= 2' in text
    assert 'required_status_checks must include one of:' in text
