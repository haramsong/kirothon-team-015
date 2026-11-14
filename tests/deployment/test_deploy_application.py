from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]
DEPLOY_SCRIPT = ROOT_DIR / "scripts" / "deployment" / "deploy-application.sh"
FIRST_DEPLOY_SCRIPT = ROOT_DIR / "scripts" / "deployment" / "first-deploy.sh"


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
        "  'remote get-url origin') printf '%s\\n' \"${FAKE_REMOTE:-https://github.com/haramsong/kirothon-team-015.git}\" ;;\n"
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
        "  cloudformation\\ describe-stacks*my-own-fridge-github-oidc*)\n"
        "    printf '%s\\n' \"${FAKE_ARTIFACT_BUCKET:-my-own-fridge-artifacts-123456}\"\n"
        "    ;;\n"
        "  cloudformation\\ describe-stacks*my-own-fridge*)\n"
        "    if [[ \"${FAKE_APP_OUTPUTS:-complete}\" == missing-api ]]; then\n"
        "      printf 'StaticBucketName\\tmy-own-fridge-static-123456\\n'\n"
        "      printf 'DistributionId\\tE123456789ABC\\n'\n"
        "    elif [[ \"${FAKE_APP_OUTPUTS:-complete}\" == invalid-distribution ]]; then\n"
        "      printf 'ApiUrl\\thttps://abc.execute-api.ap-northeast-2.amazonaws.com/\\n'\n"
        "      printf 'StaticBucketName\\tmy-own-fridge-static-123456\\n'\n"
        "      printf 'DistributionId\\tbad-id\\n'\n"
        "    else\n"
        "      printf 'DistributionId\\tE123456789ABC\\n'\n"
        "      printf 'ApiUrl\\thttps://abc.execute-api.ap-northeast-2.amazonaws.com/\\n'\n"
        "      printf 'StaticBucketName\\tmy-own-fridge-static-123456\\n'\n"
        "    fi\n"
        "    ;;\n"
        "  s3\\ sync*) [[ \"${FAKE_S3_FAIL:-0}\" == 0 ]] ;;\n"
        "  cloudfront\\ create-invalidation*) [[ \"${FAKE_INVALIDATION_FAIL:-0}\" == 0 ]] ;;\n"
        "  *) printf '지원하지 않는 fake aws 호출: %s\\n' \"$*\" >&2; exit 64 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake_aws.chmod(0o755)

    fake_sam = bin_dir / "sam"
    fake_sam.write_text(
        "#!/usr/bin/env bash\n"
        "printf 'sam %s\\n' \"$*\" >> \"${CALLS_FILE}\"\n"
        "case \"$1\" in\n"
        "  build) [[ \"${FAKE_SAM_BUILD_FAIL:-0}\" == 0 ]] ;;\n"
        "  deploy) [[ \"${FAKE_SAM_DEPLOY_FAIL:-0}\" == 0 ]] ;;\n"
        "  *) exit 64 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake_sam.chmod(0o755)

    fake_npm = bin_dir / "npm"
    fake_npm.write_text(
        "#!/usr/bin/env bash\n"
        "printf 'npm VITE_API_BASE_URL=%s %s\\n' \"${VITE_API_BASE_URL:-}\" \"$*\" >> \"${CALLS_FILE}\"\n"
        "[[ \"${FAKE_NPM_FAIL:-0}\" == 0 ]]\n",
        encoding="utf-8",
    )
    fake_npm.chmod(0o755)
    return bin_dir, calls


def run_deploy(
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
        ["bash", str(DEPLOY_SCRIPT)],
        cwd=ROOT_DIR,
        env=process_env,
        capture_output=True,
        text=True,
        check=False,
    )
    recorded_calls = calls.read_text(encoding="utf-8").splitlines()
    return result, recorded_calls


def assert_fixed_local_target(call: str) -> None:
    assert "--profile default" in call
    assert "--region ap-northeast-2" in call


def test_application_deploy_runs_guard_stack_and_frontend_steps_in_order(
    tmp_path: Path,
) -> None:
    result, calls = run_deploy(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "ApiUrl=https://abc.execute-api.ap-northeast-2.amazonaws.com" in result.stdout
    assert "StaticBucketName=my-own-fridge-static-123456" in result.stdout
    assert "DistributionId=E123456789ABC" in result.stdout

    operation_calls = [
        call
        for call in calls
        if not call.startswith("git ")
        and not call.startswith("aws sts ")
        and not call.startswith("aws configure ")
    ]
    assert [call.split()[0:2] for call in operation_calls] == [
        ["aws", "cloudformation"],
        ["sam", "build"],
        ["sam", "deploy"],
        ["aws", "cloudformation"],
        ["npm", "VITE_API_BASE_URL=https://abc.execute-api.ap-northeast-2.amazonaws.com"],
        ["aws", "s3"],
        ["aws", "cloudfront"],
    ]
    assert all(
        assert_fixed_local_target(call) is None
        for call in calls
        if call.startswith(("aws ", "sam "))
    )
    sync_call = next(call for call in calls if call.startswith("aws s3 sync"))
    assert "--delete" not in sync_call
    assert "s3://my-own-fridge-static-123456" in sync_call
    invalidation_call = next(
        call for call in calls if call.startswith("aws cloudfront create-invalidation")
    )
    assert "--distribution-id E123456789ABC" in invalidation_call
    assert "--paths /*" in invalidation_call


def test_wrong_account_stops_before_stack_or_deployment_calls(tmp_path: Path) -> None:
    result, calls = run_deploy(tmp_path, environment={"FAKE_ACCOUNT": "000000000000"})

    assert result.returncode != 0
    assert "AWS account" in result.stderr
    assert not any(
        call.startswith(("aws cloudformation", "sam ", "npm ", "aws s3", "aws cloudfront"))
        for call in calls
    )


@pytest.mark.parametrize(
    ("environment", "forbidden_prefixes"),
    [
        ({"FAKE_ARTIFACT_BUCKET": "None"}, ("sam ", "npm ", "aws s3", "aws cloudfront")),
        ({"FAKE_SAM_BUILD_FAIL": "1"}, ("sam deploy", "npm ", "aws s3", "aws cloudfront")),
        ({"FAKE_SAM_DEPLOY_FAIL": "1"}, ("npm ", "aws s3", "aws cloudfront")),
        ({"FAKE_APP_OUTPUTS": "missing-api"}, ("npm ", "aws s3", "aws cloudfront")),
        ({"FAKE_NPM_FAIL": "1"}, ("aws s3", "aws cloudfront")),
        ({"FAKE_S3_FAIL": "1"}, ("aws cloudfront",)),
    ],
)
def test_deploy_failure_prevents_all_following_mutations(
    tmp_path: Path,
    environment: dict[str, str],
    forbidden_prefixes: tuple[str, ...],
) -> None:
    result, calls = run_deploy(tmp_path, environment=environment)

    assert result.returncode != 0
    assert not any(call.startswith(forbidden_prefixes) for call in calls)


def run_first_deploy_functions(
    tmp_path: Path, *, bootstrap_fails: bool = False, arguments: tuple[str, ...] = ()
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    bin_dir, calls = write_fake_commands(tmp_path)
    process_env = os.environ.copy()
    process_env.update(
        {
            "PATH": f"{bin_dir}:{process_env['PATH']}",
            "CALLS_FILE": str(calls),
            "BOOTSTRAP_FAILS": "1" if bootstrap_fails else "0",
        }
    )
    quoted_arguments = " ".join(shlex.quote(argument) for argument in arguments)
    command = (
        f"source {shlex.quote(str(FIRST_DEPLOY_SCRIPT))}; "
        "run_bootstrap_deploy() { printf 'bootstrap\\n' >> \"${CALLS_FILE}\"; "
        "[[ \"${BOOTSTRAP_FAILS}\" == 0 ]]; }; "
        "run_application_deploy() { printf 'application\\n' >> \"${CALLS_FILE}\"; }; "
        f"main {quoted_arguments}"
    )
    result = subprocess.run(
        ["bash", "-c", command],
        cwd=ROOT_DIR,
        env=process_env,
        capture_output=True,
        text=True,
        check=False,
    )
    recorded_calls = (
        calls.read_text(encoding="utf-8").splitlines() if calls.exists() else []
    )
    return result, recorded_calls


def test_first_deploy_runs_bootstrap_before_application(tmp_path: Path) -> None:
    result, calls = run_first_deploy_functions(tmp_path)

    assert result.returncode == 0, result.stderr
    assert calls[-2:] == ["bootstrap", "application"]


def test_first_deploy_stops_when_bootstrap_fails(tmp_path: Path) -> None:
    result, calls = run_first_deploy_functions(tmp_path, bootstrap_fails=True)

    assert result.returncode != 0
    assert "bootstrap" in calls
    assert "application" not in calls


def test_first_deploy_rejects_force_or_other_arguments_before_changes(tmp_path: Path) -> None:
    result, calls = run_first_deploy_functions(tmp_path, arguments=("--force",))

    assert result.returncode == 2
    assert "인자를 받지 않습니다" in result.stderr
    assert "bootstrap" not in calls
    assert "application" not in calls


def test_deployment_scripts_contain_no_delete_or_force_operations() -> None:
    script_text = DEPLOY_SCRIPT.read_text(encoding="utf-8") + FIRST_DEPLOY_SCRIPT.read_text(
        encoding="utf-8"
    )

    assert "--delete" not in script_text
    assert "delete-stack" not in script_text
    assert "delete-bucket" not in script_text
    assert "--force" not in script_text
