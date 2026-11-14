import os
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
VERIFY_SCRIPT = ROOT_DIR / "scripts" / "verify-all.sh"


def _write_recorder(path: Path, label: str) -> None:
    path.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s %s\\n' '" + label + "' \"$*\" >> \"${COMMAND_LOG}\"\n"
        "if [[ -n \"${FAIL_MATCH:-}\" && \"$*\" == *\"${FAIL_MATCH}\"* ]]; then\n"
        "  exit \"${FAIL_CODE:-1}\"\n"
        "fi\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _run_with_recorders(tmp_path: Path, **extra_env: str) -> subprocess.CompletedProcess[str]:
    python_recorder = tmp_path / "python-recorder"
    npm_recorder = tmp_path / "npm-recorder"
    command_log = tmp_path / "commands.log"
    _write_recorder(python_recorder, "python")
    _write_recorder(npm_recorder, "npm")

    env = {
        **os.environ,
        "BACKEND_PYTHON": str(python_recorder),
        "NPM_BIN": str(npm_recorder),
        "COMMAND_LOG": str(command_log),
        **extra_env,
    }
    result = subprocess.run(
        [str(VERIFY_SCRIPT)],
        cwd=ROOT_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    result.command_log = command_log.read_text(encoding="utf-8").splitlines()
    return result


def test_verify_all_runs_core_then_optional_meal_tests_and_build(tmp_path: Path) -> None:
    result = _run_with_recorders(tmp_path)

    assert result.returncode == 0, result.stderr
    assert len(result.command_log) == 7
    assert "test_receipt_registration_recommendation_recipe_and_atomic_deduction_flow" in result.command_log[0]
    assert "--ignore=" in result.command_log[1]
    assert "run test --" in result.command_log[2]
    assert "test_meal_plan_api.py" in result.command_log[3]
    assert "src/features/meal-plan/MealPlanPage.test.tsx" in result.command_log[4]
    assert result.command_log[5].endswith("run typecheck")
    assert result.command_log[6].endswith("run build")


def test_verify_all_preserves_failure_code_and_stops(tmp_path: Path) -> None:
    result = _run_with_recorders(
        tmp_path,
        FAIL_MATCH="test_receipt_registration_recommendation_recipe_and_atomic_deduction_flow",
        FAIL_CODE="23",
    )

    assert result.returncode == 23
    assert len(result.command_log) == 1
    assert "검증 실패 (23): 핵심 데모 종단 간 테스트" in result.stderr
