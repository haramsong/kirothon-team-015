from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
BOOTSTRAP_TEMPLATE = ROOT_DIR / "infra" / "github-oidc-bootstrap.yaml"
CD_WORKFLOW = ROOT_DIR / ".github" / "workflows" / "cd.yml"
IMMUTABLE_SUBJECT = (
    "repo:haramsong@61612250/kirothon-team-015@1457328764:ref:refs/heads/main"
)
LEGACY_SUBJECT = "repo:haramsong/kirothon-team-015:ref:refs/heads/main"


def test_bootstrap_trust_uses_repository_immutable_subject() -> None:
    template = BOOTSTRAP_TEMPLATE.read_text(encoding="utf-8")

    assert f"token.actions.githubusercontent.com:sub: {IMMUTABLE_SUBJECT}" in template
    assert f"token.actions.githubusercontent.com:sub: {LEGACY_SUBJECT}" not in template


def test_cd_uses_supported_oidc_inputs_and_checks_assumed_account() -> None:
    workflow = CD_WORKFLOW.read_text(encoding="utf-8")
    oidc_step = workflow.index("uses: aws-actions/configure-aws-credentials@v4")
    account_check = workflow.index("aws sts get-caller-identity")

    assert "allowed-account-ids:" not in workflow
    assert "role-to-assume: ${{ env.AWS_ROLE_ARN }}" in workflow
    assert "aws-region: ${{ env.AWS_REGION }}" in workflow
    assert oidc_step < account_check
    assert "[[ \"${actual_account}\" == '462747820533' ]]" in workflow
