from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]
ASSERT_SCRIPT = ROOT_DIR / "scripts" / "deployment" / "assert-target.sh"


def run_bash(command: str, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    process_env = os.environ.copy()
    if env is not None:
        process_env.update(env)
    return subprocess.run(
        ["bash", "-c", command],
        cwd=ROOT_DIR,
        env=process_env,
        capture_output=True,
        text=True,
        check=False,
    )


def source_assert_script(command: str) -> str:
    return f"source {shlex.quote(str(ASSERT_SCRIPT))}; {command}"


def test_approved_constants_and_targets_match_exactly() -> None:
    result = run_bash(
        source_assert_script(
            "assert_github_target "
            "'haramsong/kirothon-team-015' 'refs/heads/main' "
            "'462747820533' 'ap-northeast-2'; "
            "printf '%s|%s|%s|%s|%s|%s' "
            '"${AWS_PROFILE}" "${AWS_REGION}" "${GITHUB_REPOSITORY}" '
            '"${DEPLOY_BRANCH}" "${BOOTSTRAP_STACK_NAME}" "${SAM_STACK_NAME}"'
        )
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "default|ap-northeast-2|haramsong/kirothon-team-015|main|"
        "my-own-fridge-github-oidc|my-own-fridge"
    )


@pytest.mark.parametrize(
    ("repository", "ref", "account", "region"),
    [
        ("other/kirothon-team-015", "refs/heads/main", "462747820533", "ap-northeast-2"),
        ("haramsong/kirothon-team-015", "refs/heads/dev", "462747820533", "ap-northeast-2"),
        ("haramsong/kirothon-team-015", "refs/heads/main", "000000000000", "ap-northeast-2"),
        ("haramsong/kirothon-team-015", "refs/heads/main", "462747820533", "us-east-1"),
    ],
)
def test_github_mismatch_blocks_change_runner(
    tmp_path: Path,
    repository: str,
    ref: str,
    account: str,
    region: str,
) -> None:
    marker = tmp_path / "change-ran"
    command = source_assert_script(
        "record_change() { touch \"${CHANGE_MARKER}\"; }; "
        f"run_after_github_target_check {shlex.quote(repository)} {shlex.quote(ref)} "
        f"{shlex.quote(account)} {shlex.quote(region)} record_change"
    )

    result = run_bash(command, env={"CHANGE_MARKER": str(marker)})

    assert result.returncode != 0
    assert "배포 대상 불일치" in result.stderr
    assert not marker.exists()


def test_local_target_reads_default_profile_and_region_before_running(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "aws-calls"
    marker = tmp_path / "change-ran"
    fake_aws = bin_dir / "aws"
    fake_aws.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$*\" >> \"${AWS_CALLS}\"\n"
        "if [[ \"$1 $2\" == 'sts get-caller-identity' ]]; then\n"
        "  printf '462747820533\\n'\n"
        "elif [[ \"$1 $2 $3\" == 'configure get region' ]]; then\n"
        "  printf 'ap-northeast-2\\n'\n"
        "else\n"
        "  exit 64\n"
        "fi\n",
        encoding="utf-8",
    )
    fake_aws.chmod(0o755)
    command = source_assert_script(
        "record_change() { touch \"${CHANGE_MARKER}\"; }; "
        "run_after_local_target_check record_change"
    )

    result = run_bash(
        command,
        env={
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "AWS_CALLS": str(calls),
            "CHANGE_MARKER": str(marker),
        },
    )

    assert result.returncode == 0, result.stderr
    assert marker.exists()
    assert calls.read_text(encoding="utf-8").splitlines() == [
        "sts get-caller-identity --query Account --output text --profile default --region ap-northeast-2",
        "configure get region --profile default --region ap-northeast-2",
    ]


def test_local_account_mismatch_blocks_change_runner(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    marker = tmp_path / "change-ran"
    fake_aws = bin_dir / "aws"
    fake_aws.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$1 $2\" == 'sts get-caller-identity' ]]; then\n"
        "  printf '000000000000\\n'\n"
        "else\n"
        "  printf 'ap-northeast-2\\n'\n"
        "fi\n",
        encoding="utf-8",
    )
    fake_aws.chmod(0o755)
    command = source_assert_script(
        "record_change() { touch \"${CHANGE_MARKER}\"; }; "
        "run_after_local_target_check record_change"
    )

    result = run_bash(
        command,
        env={"PATH": f"{bin_dir}:{os.environ['PATH']}", "CHANGE_MARKER": str(marker)},
    )

    assert result.returncode != 0
    assert "AWS account" in result.stderr
    assert not marker.exists()
