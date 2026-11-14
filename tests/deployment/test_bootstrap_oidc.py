from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]
BOOTSTRAP_SCRIPT = ROOT_DIR / "scripts" / "deployment" / "bootstrap-oidc.sh"
BOOTSTRAP_TEMPLATE = ROOT_DIR / "infra" / "github-oidc-bootstrap.yaml"
EXPECTED_PROVIDER_ARN = (
    "arn:aws:iam::462747820533:oidc-provider/token.actions.githubusercontent.com"
)


def write_fake_commands(tmp_path: Path) -> tuple[Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls.log"

    fake_git = bin_dir / "git"
    fake_git.write_text(
        "#!/usr/bin/env bash\n"
        "printf 'git %s\\n' \"$*\" >> \"${CALLS_FILE}\"\n"
        "case \"$*\" in\n"
        "  'branch --show-current') printf '%s\\n' \"${FAKE_BRANCH:-main}\" ;;\n"
        "  'remote get-url origin') printf '%s\\n' "
        "\"${FAKE_REMOTE:-https://github.com/haramsong/my-own-fridge.git}\" ;;\n"
        "  *) exit 64 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake_git.chmod(0o755)

    fake_aws = bin_dir / "aws"
    fake_aws.write_text(
        "#!/usr/bin/env bash\n"
        "printf 'aws %s\\n' \"$*\" >> \"${CALLS_FILE}\"\n"
        "case \"$*\" in\n"
        "  sts\\ get-caller-identity*) printf '%s\\n' \"${FAKE_ACCOUNT:-462747820533}\" ;;\n"
        "  configure\\ get\\ region*) printf '%s\\n' \"${FAKE_REGION:-ap-northeast-2}\" ;;\n"
        "  iam\\ list-open-id-connect-providers*) printf '%s\\n' \"${FAKE_PROVIDER_LIST:-}\" ;;\n"
        "  iam\\ get-open-id-connect-provider*) "
        "printf '%s\\n' \"${FAKE_PROVIDER_URL:-token.actions.githubusercontent.com}\" ;;\n"
        "  cloudformation\\ validate-template*) "
        "[[ \"${FAKE_VALIDATE_FAIL:-0}\" == 0 ]] ;;\n"
        "  cloudformation\\ describe-stacks*StackStatus*)\n"
        "    if [[ \"${FAKE_STACK_EXISTS:-0}\" == 1 ]]; then\n"
        "      printf 'CREATE_COMPLETE\\n'\n"
        "    else\n"
        "      printf 'Stack with id my-own-fridge-github-oidc does not exist\\n' >&2\n"
        "      exit 255\n"
        "    fi\n"
        "    ;;\n"
        "  cloudformation\\ deploy*) [[ \"${FAKE_DEPLOY_FAIL:-0}\" == 0 ]] ;;\n"
        "  cloudformation\\ wait*) [[ \"${FAKE_WAIT_FAIL:-0}\" == 0 ]] ;;\n"
        "  cloudformation\\ describe-stacks*GitHubDeploymentRoleArn*)\n"
        "    printf '%s\\n' \"${FAKE_ROLE_ARN:-arn:aws:iam::462747820533:role/my-own-fridge-github-deploy}\"\n"
        "    ;;\n"
        "  cloudformation\\ describe-stacks*SamArtifactBucketName*)\n"
        "    printf '%s\\n' \"${FAKE_BUCKET:-my-own-fridge-artifacts-123456}\"\n"
        "    ;;\n"
        "  *) printf '지원하지 않는 fake aws 호출: %s\\n' \"$*\" >&2; exit 64 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake_aws.chmod(0o755)
    return bin_dir, calls


def run_bootstrap(
    tmp_path: Path, *, environment: dict[str, str] | None = None
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    bin_dir, calls = write_fake_commands(tmp_path)
    process_env = os.environ.copy()
    process_env.update(
        {
            "PATH": f"{bin_dir}:{process_env['PATH']}",
            "CALLS_FILE": str(calls),
        }
    )
    if environment:
        process_env.update(environment)

    result = subprocess.run(
        ["bash", str(BOOTSTRAP_SCRIPT)],
        cwd=ROOT_DIR,
        env=process_env,
        capture_output=True,
        text=True,
        check=False,
    )
    recorded_calls = calls.read_text(encoding="utf-8").splitlines()
    return result, recorded_calls


def aws_calls(recorded_calls: list[str]) -> list[str]:
    return [call for call in recorded_calls if call.startswith("aws ")]


def assert_fixed_aws_target(call: str) -> None:
    assert "--profile default" in call
    assert "--region ap-northeast-2" in call


def test_bootstrap_runs_guard_discovery_validation_deploy_wait_and_outputs_in_order(
    tmp_path: Path,
) -> None:
    result, calls = run_bootstrap(tmp_path)

    assert result.returncode == 0, result.stderr
    assert '"GitHubDeploymentRoleArn": "arn:aws:iam::462747820533:role/' in result.stdout
    assert '"SamArtifactBucketName": "my-own-fridge-artifacts-123456"' in result.stdout

    recorded_aws_calls = aws_calls(calls)
    assert all(assert_fixed_aws_target(call) is None for call in recorded_aws_calls)
    command_names = [" ".join(call.split()[1:3]) for call in recorded_aws_calls]
    assert command_names == [
        "sts get-caller-identity",
        "configure get",
        "iam list-open-id-connect-providers",
        "cloudformation validate-template",
        "cloudformation deploy",
        "cloudformation wait",
        "cloudformation describe-stacks",
        "cloudformation describe-stacks",
    ]
    assert "cloudformation wait stack-exists" in recorded_aws_calls[5]
    deploy_call = recorded_aws_calls[4]
    assert "--no-fail-on-empty-changeset" in deploy_call
    assert "--no-confirm-changeset" not in deploy_call


def test_bootstrap_role_description_uses_iam_compatible_ascii() -> None:
    template = BOOTSTRAP_TEMPLATE.read_text(encoding="utf-8")
    role_description = next(
        line.split("Description:", maxsplit=1)[1].strip()
        for line in template.splitlines()
        if line.strip().startswith("Description:")
        and "GitHub Actions OIDC deployment role" in line
    )

    assert role_description == "GitHub Actions OIDC deployment role for my-own-fridge"
    assert role_description.isascii()


def test_wrong_account_stops_before_provider_discovery_or_changes(tmp_path: Path) -> None:
    result, calls = run_bootstrap(tmp_path, environment={"FAKE_ACCOUNT": "000000000000"})

    assert result.returncode != 0
    assert "AWS account" in result.stderr
    assert not any("iam " in call or "cloudformation " in call for call in calls)


def test_duplicate_github_providers_stop_before_template_validation(tmp_path: Path) -> None:
    provider_list = f"{EXPECTED_PROVIDER_ARN} {EXPECTED_PROVIDER_ARN}"
    result, calls = run_bootstrap(
        tmp_path,
        environment={"FAKE_PROVIDER_LIST": provider_list},
    )

    assert result.returncode != 0
    assert "여러 개" in result.stderr
    assert not any("cloudformation " in call for call in calls)


def test_template_validation_failure_stops_before_stack_lookup_and_deploy(tmp_path: Path) -> None:
    result, calls = run_bootstrap(tmp_path, environment={"FAKE_VALIDATE_FAIL": "1"})

    assert result.returncode != 0
    assert not any("cloudformation describe-stacks" in call for call in calls)
    assert not any("cloudformation deploy" in call for call in calls)


@pytest.mark.parametrize("failure", ["FAKE_DEPLOY_FAIL", "FAKE_WAIT_FAIL"])
def test_stack_failure_does_not_read_or_print_outputs(tmp_path: Path, failure: str) -> None:
    result, calls = run_bootstrap(tmp_path, environment={failure: "1"})

    assert result.returncode != 0
    assert "GitHubDeploymentRoleArn" not in result.stdout
    output_calls = [
        call
        for call in calls
        if "GitHubDeploymentRoleArn" in call or "SamArtifactBucketName" in call
    ]
    assert output_calls == []
