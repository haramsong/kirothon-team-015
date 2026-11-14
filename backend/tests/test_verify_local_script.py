import os
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
VERIFY_LOCAL_SCRIPT = ROOT_DIR / "scripts" / "verify-local.sh"


def _write_recorder(path: Path, label: str) -> None:
    path.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s %s\\n' '" + label + "' \"$*\" >> \"${COMMAND_LOG}\"\n"
        "if [[ -n \"${FAIL_LABEL:-}\" && '" + label + "' == \"${FAIL_LABEL}\" ]]; then\n"
        "  exit \"${FAIL_CODE:-1}\"\n"
        "fi\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _run_with_recorders(tmp_path: Path, **extra_env: str) -> subprocess.CompletedProcess[str]:
    smoke_recorder = tmp_path / "smoke-recorder"
    verify_recorder = tmp_path / "verify-recorder"
    sam_recorder = tmp_path / "sam-recorder"
    command_log = tmp_path / "commands.log"
    _write_recorder(smoke_recorder, "smoke")
    _write_recorder(verify_recorder, "verify")
    _write_recorder(sam_recorder, "sam")

    env = {
        **os.environ,
        "SMOKE_SCRIPT": str(smoke_recorder),
        "VERIFY_SCRIPT": str(verify_recorder),
        "SAM_BIN": str(sam_recorder),
        "COMMAND_LOG": str(command_log),
        **extra_env,
    }
    result = subprocess.run(
        [str(VERIFY_LOCAL_SCRIPT)],
        cwd=ROOT_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    result.command_log = command_log.read_text(encoding="utf-8").splitlines()
    return result


def test_verify_local_runs_smoke_and_tests_before_sam_commands(tmp_path: Path) -> None:
    result = _run_with_recorders(tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.command_log == [
        "smoke ",
        "verify ",
        "sam validate --profile default --region ap-northeast-2",
        "sam build --profile default --region ap-northeast-2",
    ]


def test_verify_local_stops_before_sam_when_full_verification_fails(tmp_path: Path) -> None:
    result = _run_with_recorders(
        tmp_path,
        FAIL_LABEL="verify",
        FAIL_CODE="29",
    )

    assert result.returncode == 29
    assert result.command_log == ["smoke ", "verify "]
    assert "검증 실패 (29): 전체 자동 테스트와 프로덕션 빌드" in result.stderr


def test_verify_local_preserves_sam_failure_code_and_skips_build(tmp_path: Path) -> None:
    result = _run_with_recorders(
        tmp_path,
        FAIL_LABEL="sam",
        FAIL_CODE="37",
    )

    assert result.returncode == 37
    assert result.command_log == [
        "smoke ",
        "verify ",
        "sam validate --profile default --region ap-northeast-2",
    ]
    assert "검증 실패 (37): SAM 템플릿 검증" in result.stderr
