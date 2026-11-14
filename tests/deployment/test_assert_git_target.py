from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]
ASSERT_SCRIPT = ROOT_DIR / "scripts" / "deployment" / "assert-git-target.sh"


def run_bash(command: str, *, cwd: Path = ROOT_DIR) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", command],
        cwd=cwd,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )


def source_assert_script(command: str) -> str:
    return f"source {shlex.quote(str(ASSERT_SCRIPT))}; {command}"


def git(repo: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def init_repository(tmp_path: Path, *, branch: str = "main") -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    result = git(repo, "init", "-b", branch)
    assert result.returncode == 0, result.stderr
    result = git(repo, "remote", "add", "origin", "https://github.com/haramsong/my-own-fridge.git")
    assert result.returncode == 0, result.stderr
    return repo


@pytest.mark.parametrize(
    "remote_url",
    [
        "https://github.com/haramsong/my-own-fridge.git",
        "https://github.com/haramsong/my-own-fridge",
        "git@github.com:haramsong/my-own-fridge.git",
        "ssh://git@github.com/haramsong/my-own-fridge.git",
    ],
)
def test_normalize_github_remote_accepts_approved_https_and_ssh(remote_url: str) -> None:
    result = run_bash(source_assert_script(f"normalize_github_remote {shlex.quote(remote_url)}"))

    assert result.returncode == 0, result.stderr
    assert result.stdout == "haramsong/my-own-fridge\n"


@pytest.mark.parametrize(
    "remote_url",
    [
        "https://github.example.com/haramsong/my-own-fridge.git",
        "https://github.com/haramsong/my-own-fridge/other",
        "git@github.com:someone/my-own-fridge.git",
    ],
)
def test_git_target_rejects_unapproved_or_ambiguous_remote(remote_url: str) -> None:
    result = run_bash(
        source_assert_script(f"assert_git_target_values main {shlex.quote(remote_url)}")
    )

    assert result.returncode != 0
    assert "Git 안전 검사 실패" in result.stderr


def test_current_target_rejects_non_main_branch(tmp_path: Path) -> None:
    repo = init_repository(tmp_path, branch="feature/task")

    result = run_bash(source_assert_script("assert_current_git_target"), cwd=repo)

    assert result.returncode != 0
    assert "branch가 승인된 값과 다릅니다" in result.stderr


def test_stage_task_paths_stages_only_exact_allowlist_and_preserves_other_changes(
    tmp_path: Path,
) -> None:
    repo = init_repository(tmp_path)
    allowed = repo / "allowed.txt"
    unrelated = repo / "unrelated.txt"
    allowed.write_text("task change\n", encoding="utf-8")
    unrelated.write_text("other change\n", encoding="utf-8")

    result = run_bash(source_assert_script("stage_task_paths allowed.txt"), cwd=repo)

    assert result.returncode == 0, result.stderr
    staged = git(repo, "diff", "--cached", "--name-only")
    unstaged = git(repo, "status", "--short")
    assert staged.stdout.splitlines() == ["allowed.txt"]
    assert "?? unrelated.txt" in unstaged.stdout


def test_stage_task_paths_rejects_existing_staged_file_outside_allowlist(tmp_path: Path) -> None:
    repo = init_repository(tmp_path)
    (repo / "allowed.txt").write_text("task change\n", encoding="utf-8")
    (repo / "unrelated.txt").write_text("other change\n", encoding="utf-8")
    staged = git(repo, "add", "--", "unrelated.txt")
    assert staged.returncode == 0, staged.stderr

    result = run_bash(source_assert_script("stage_task_paths allowed.txt"), cwd=repo)

    assert result.returncode != 0
    assert "allowlist 밖의 파일이 이미 stage되어 있습니다: unrelated.txt" in result.stderr
    assert git(repo, "diff", "--cached", "--name-only").stdout.splitlines() == ["unrelated.txt"]


@pytest.mark.parametrize(
    "protected_path",
    [
        ".kiro/specs/refrigerator-management-mvp/tasks.md",
        ".kiro/specs/refrigerator-management-mvp/nested/file.md",
        ".kiro/agents/designer.json",
    ],
)
def test_stage_task_paths_rejects_protected_mvp_and_designer_paths(
    tmp_path: Path,
    protected_path: str,
) -> None:
    repo = init_repository(tmp_path)
    target = repo / protected_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("unrelated change\n", encoding="utf-8")

    result = run_bash(
        source_assert_script(f"stage_task_paths {shlex.quote(protected_path)}"),
        cwd=repo,
    )

    assert result.returncode != 0
    assert "stage가 금지된 경로" in result.stderr
    assert git(repo, "diff", "--cached", "--name-only").stdout == ""


@pytest.mark.parametrize(
    "forbidden_argument",
    [
        "--force",
        "--force-with-lease",
        "--force-with-lease=main:deadbeef",
        "--force-if-includes",
        "-f",
        "--no-verify",
        "-n",
        "+main:main",
    ],
)
def test_forbidden_force_and_hook_bypass_flags_are_rejected(forbidden_argument: str) -> None:
    result = run_bash(
        source_assert_script(f"assert_safe_git_flags {shlex.quote(forbidden_argument)}")
    )

    assert result.returncode != 0
    assert "Git 안전 검사 실패" in result.stderr


def test_safe_flags_are_accepted() -> None:
    result = run_bash(source_assert_script("assert_safe_git_flags -m 'task commit' origin main"))

    assert result.returncode == 0, result.stderr


def test_stage_task_paths_uses_repository_relative_path_from_subdirectory(tmp_path: Path) -> None:
    repo = init_repository(tmp_path)
    (repo / "allowed.txt").write_text("task change\n", encoding="utf-8")
    subdirectory = repo / "nested"
    subdirectory.mkdir()

    result = run_bash(source_assert_script("stage_task_paths allowed.txt"), cwd=subdirectory)

    assert result.returncode == 0, result.stderr
    assert git(repo, "diff", "--cached", "--name-only").stdout.splitlines() == ["allowed.txt"]


def test_stage_task_paths_rejects_directory_allowlist(tmp_path: Path) -> None:
    repo = init_repository(tmp_path)
    directory = repo / "task-files"
    directory.mkdir()
    (directory / "one.txt").write_text("task change\n", encoding="utf-8")

    result = run_bash(source_assert_script("stage_task_paths task-files"), cwd=repo)

    assert result.returncode != 0
    assert "정확한 파일 경로만 사용할 수 있습니다" in result.stderr
    assert git(repo, "diff", "--cached", "--name-only").stdout == ""
