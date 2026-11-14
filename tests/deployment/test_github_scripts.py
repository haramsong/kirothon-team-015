from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIGURE_SCRIPT = ROOT_DIR / "scripts" / "deployment" / "configure-github.sh"
DISPATCH_SCRIPT = ROOT_DIR / "scripts" / "deployment" / "dispatch-cd.sh"
ROLE_ARN = "arn:aws:iam::462747820533:role/my-own-fridge-github-deploy"
ARTIFACT_BUCKET = "my-own-fridge-artifacts-123456"
MAIN_SHA = "a" * 40


def write_fake_commands(tmp_path: Path, *, include_gh: bool = True) -> tuple[Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls.log"

    fake_git = bin_dir / "git"
    fake_git.write_text(
        "#!/bin/bash\n"
        "printf 'git %s\\n' \"$*\" >> \"${CALLS_FILE}\"\n"
        "case \"$*\" in\n"
        "  'branch --show-current') printf '%s\\n' \"${FAKE_BRANCH:-main}\" ;;\n"
        "  'remote get-url origin') printf '%s\\n' "
        "\"${FAKE_REMOTE:-https://github.com/haramsong/my-own-fridge.git}\" ;;\n"
        "  'ls-remote --exit-code origin refs/heads/main') "
        "printf '%s\\trefs/heads/main\\n' \"${FAKE_MAIN_SHA:-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa}\" ;;\n"
        "  *) exit 64 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake_git.chmod(0o755)

    fake_aws = bin_dir / "aws"
    fake_aws.write_text(
        "#!/bin/bash\n"
        "printf 'aws %s\\n' \"$*\" >> \"${CALLS_FILE}\"\n"
        "case \"$*\" in\n"
        "  sts\\ get-caller-identity*) printf '%s\\n' \"${FAKE_ACCOUNT:-462747820533}\" ;;\n"
        "  configure\\ get\\ region*) printf '%s\\n' \"${FAKE_REGION:-ap-northeast-2}\" ;;\n"
        "  cloudformation\\ describe-stacks*GitHubDeploymentRoleArn*)\n"
        "    printf '%s\\n' \"${FAKE_ROLE_ARN:-arn:aws:iam::462747820533:role/my-own-fridge-github-deploy}\"\n"
        "    ;;\n"
        "  cloudformation\\ describe-stacks*SamArtifactBucketName*)\n"
        "    printf '%s\\n' \"${FAKE_BUCKET:-my-own-fridge-artifacts-123456}\"\n"
        "    ;;\n"
        "  *) exit 64 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake_aws.chmod(0o755)

    fake_sleep = bin_dir / "sleep"
    fake_sleep.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    fake_sleep.chmod(0o755)

    if include_gh:
        fake_gh = bin_dir / "gh"
        fake_gh.write_text(
            "#!/bin/bash\n"
            "printf 'gh %s\\n' \"$*\" >> \"${CALLS_FILE}\"\n"
            "case \"$1 $2\" in\n"
            "  'auth status') [[ \"${FAKE_GH_AUTH_FAIL:-0}\" == 0 ]] ;;\n"
            "  'repo view') printf '%s\\n' \"${FAKE_GH_REPOSITORY:-haramsong/my-own-fridge}\" ;;\n"
            "  'variable set')\n"
            "    [[ \"${FAKE_VARIABLE_SET_FAIL_NAME:-}\" != \"$3\" ]]\n"
            "    ;;\n"
            "  'variable list')\n"
            "    printf 'AWS_ROLE_ARN\\t%s\\n' \"${FAKE_LIST_ROLE_ARN:-arn:aws:iam::462747820533:role/my-own-fridge-github-deploy}\"\n"
            "    printf 'AWS_REGION\\t%s\\n' \"${FAKE_LIST_REGION:-ap-northeast-2}\"\n"
            "    printf 'SAM_STACK_NAME\\t%s\\n' \"${FAKE_LIST_STACK_NAME:-my-own-fridge}\"\n"
            "    if [[ \"${FAKE_LIST_OMIT_BUCKET:-0}\" == 0 ]]; then\n"
            "      printf 'SAM_ARTIFACT_BUCKET\\t%s\\n' \"${FAKE_LIST_BUCKET:-my-own-fridge-artifacts-123456}\"\n"
            "    fi\n"
            "    ;;\n"
            "  'workflow run') [[ \"${FAKE_WORKFLOW_RUN_FAIL:-0}\" == 0 ]] ;;\n"
            "  'run list')\n"
            "    count=0\n"
            "    [[ -f \"${GH_LIST_COUNT_FILE}\" ]] && count=$(<\"${GH_LIST_COUNT_FILE}\")\n"
            "    count=$((count + 1))\n"
            "    printf '%s' \"${count}\" > \"${GH_LIST_COUNT_FILE}\"\n"
            "    if (( count == 1 )); then\n"
            "      printf '100\\n'\n"
            "    else\n"
            "      printf '101\\n100\\n'\n"
            "    fi\n"
            "    ;;\n"
            "  'run watch') [[ \"${FAKE_WATCH_FAIL:-0}\" == 0 ]] ;;\n"
            "  'run view')\n"
            "    printf '%s\\t%s\\t%s\\n' "
            "\"${FAKE_CONCLUSION:-success}\" "
            "\"${FAKE_HEAD_SHA:-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa}\" "
            "'https://github.com/haramsong/my-own-fridge/actions/runs/101'\n"
            "    ;;\n"
            "  *) exit 64 ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        fake_gh.chmod(0o755)

    return bin_dir, calls


def run_script(
    tmp_path: Path,
    script: Path,
    *,
    arguments: tuple[str, ...] = (),
    environment: dict[str, str] | None = None,
    include_gh: bool = True,
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    bin_dir, calls = write_fake_commands(tmp_path, include_gh=include_gh)
    process_env = os.environ.copy()
    process_env.update(
        {
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "CALLS_FILE": str(calls),
            "GH_LIST_COUNT_FILE": str(tmp_path / "gh-list-count"),
            "DISPATCH_RUN_LOOKUP_ATTEMPTS": "2",
            "DISPATCH_RUN_LOOKUP_DELAY_SECONDS": "0",
        }
    )
    if environment:
        process_env.update(environment)

    result = subprocess.run(
        ["/bin/bash", str(script), *arguments],
        cwd=ROOT_DIR,
        env=process_env,
        capture_output=True,
        text=True,
        check=False,
    )
    recorded_calls = calls.read_text(encoding="utf-8").splitlines() if calls.exists() else []
    return result, recorded_calls


def test_configure_sets_only_allowlisted_variables_and_verifies_values(tmp_path: Path) -> None:
    result, calls = run_script(tmp_path, CONFIGURE_SCRIPT)

    assert result.returncode == 0, result.stderr
    variable_set_calls = [call for call in calls if call.startswith("gh variable set")]
    assert [call.split()[3] for call in variable_set_calls] == [
        "AWS_ROLE_ARN",
        "AWS_REGION",
        "SAM_STACK_NAME",
        "SAM_ARTIFACT_BUCKET",
    ]
    assert all("--repo haramsong/my-own-fridge" in call for call in variable_set_calls)
    assert all(
        forbidden not in "\n".join(calls)
        for forbidden in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")
    )
    assert calls.index(variable_set_calls[-1]) < next(
        index for index, call in enumerate(calls) if call.startswith("gh variable list")
    )
    assert "네 개를 설정하고" in result.stdout
    aws_calls = [call for call in calls if call.startswith("aws ")]
    assert all("--profile default" in call for call in aws_calls)
    assert all("--region ap-northeast-2" in call for call in aws_calls)


def test_configure_rejects_all_arguments_before_external_calls(tmp_path: Path) -> None:
    result, calls = run_script(
        tmp_path,
        CONFIGURE_SCRIPT,
        arguments=("AWS_ACCESS_KEY_ID", "value"),
    )

    assert result.returncode == 2
    assert "인자로 받지 않습니다" in result.stderr
    assert calls == []


@pytest.mark.parametrize("include_gh,environment", [(False, None), (True, {"FAKE_GH_AUTH_FAIL": "1"})])
def test_configure_missing_or_unauthenticated_gh_prints_manual_commands_without_changes(
    tmp_path: Path,
    include_gh: bool,
    environment: dict[str, str] | None,
) -> None:
    result, calls = run_script(
        tmp_path,
        CONFIGURE_SCRIPT,
        include_gh=include_gh,
        environment=environment,
    )

    assert result.returncode != 0
    assert "gh variable set AWS_ROLE_ARN" in result.stderr
    assert "gh variable set SAM_ARTIFACT_BUCKET" in result.stderr
    assert not any(call.startswith("gh variable set") for call in calls)


def test_configure_invalid_bootstrap_output_stops_before_github_changes(tmp_path: Path) -> None:
    result, calls = run_script(
        tmp_path,
        CONFIGURE_SCRIPT,
        environment={"FAKE_BUCKET": "None"},
    )

    assert result.returncode != 0
    assert "bucket 이름 형식" in result.stderr
    assert not any(call.startswith("gh ") for call in calls)


def test_variable_set_function_rejects_non_allowlisted_aws_key_name(tmp_path: Path) -> None:
    bin_dir, calls = write_fake_commands(tmp_path)
    process_env = os.environ.copy()
    process_env.update(
        {
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "CALLS_FILE": str(calls),
            "GH_LIST_COUNT_FILE": str(tmp_path / "gh-list-count"),
        }
    )
    command = (
        f"source {shlex.quote(str(CONFIGURE_SCRIPT))}; "
        "set_repository_variable AWS_ACCESS_KEY_ID forbidden"
    )
    result = subprocess.run(
        ["/bin/bash", "-c", command],
        cwd=ROOT_DIR,
        env=process_env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "허용되지 않은" in result.stderr
    assert not any(
        call.startswith("gh variable set")
        for call in (calls.read_text(encoding="utf-8").splitlines() if calls.exists() else [])
    )


def test_dispatch_runs_cd_for_main_and_verifies_new_run_sha(tmp_path: Path) -> None:
    result, calls = run_script(tmp_path, DISPATCH_SCRIPT)

    assert result.returncode == 0, result.stderr
    assert (
        "gh workflow run cd.yml --repo haramsong/my-own-fridge --ref main" in calls
    )
    assert any(
        call.startswith("gh run list")
        and "--workflow cd.yml" in call
        and "--event workflow_dispatch" in call
        and "--branch main" in call
        and f"--commit {MAIN_SHA}" in call
        for call in calls
    )
    assert "gh run watch 101 --repo haramsong/my-own-fridge --exit-status" in calls
    assert "gh run view 101 --repo haramsong/my-own-fridge" in "\n".join(calls)
    assert f"head_sha={MAIN_SHA}" in result.stdout


def test_dispatch_rejects_sha_different_from_origin_main_before_github_call(tmp_path: Path) -> None:
    result, calls = run_script(tmp_path, DISPATCH_SCRIPT, arguments=("b" * 40,))

    assert result.returncode != 0
    assert "origin/main과 다릅니다" in result.stderr
    assert not any(call.startswith("gh ") for call in calls)


def test_dispatch_unauthenticated_gh_prints_manual_commands_without_dispatch(tmp_path: Path) -> None:
    result, calls = run_script(
        tmp_path,
        DISPATCH_SCRIPT,
        environment={"FAKE_GH_AUTH_FAIL": "1"},
    )

    assert result.returncode != 0
    assert "gh workflow run cd.yml --repo haramsong/my-own-fridge --ref main" in result.stderr
    assert f"--commit {MAIN_SHA}" in result.stderr
    assert not any(call.startswith("gh workflow run") for call in calls)


@pytest.mark.parametrize(
    ("environment", "expected_error"),
    [
        ({"FAKE_CONCLUSION": "failure"}, "성공하지 않았습니다"),
        ({"FAKE_HEAD_SHA": "b" * 40}, "head SHA가 요청 revision과 다릅니다"),
    ],
)
def test_dispatch_fails_when_conclusion_or_head_sha_does_not_match(
    tmp_path: Path,
    environment: dict[str, str],
    expected_error: str,
) -> None:
    result, calls = run_script(
        tmp_path,
        DISPATCH_SCRIPT,
        environment=environment,
    )

    assert result.returncode != 0
    assert expected_error in result.stderr
    assert any(call.startswith("gh run view 101") for call in calls)
