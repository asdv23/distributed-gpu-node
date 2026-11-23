"""scripts/publish_reports.sh against throwaway git repositories. Report contents are SIMULATED."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "publish_reports.sh"
# never reach the caller's repository or read the caller's git configuration
ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")} | {
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
FINISHED, UNFINISHED = "2000-01-01", "2999-01-01"  # before and after any real "today"


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True, env=ENV).stdout


def publish(work: Path) -> subprocess.CompletedProcess:
    return subprocess.run([str(work / "scripts" / "publish_reports.sh")], capture_output=True, text=True, env=ENV)


def report(work: Path, day: str) -> str:
    path = f"reports/market/{day}.md"
    (work / path).write_text("SIMULATED report\n")
    return path


def subjects(remote: Path) -> list[str]:
    return git(remote, "log", "--format=%s", "main").splitlines()


@pytest.fixture
def repos(tmp_path):
    remote, work = tmp_path / "remote.git", tmp_path / "work"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
    git(tmp_path, "clone", "-q", str(remote), str(work))
    git(work, "symbolic-ref", "HEAD", "refs/heads/main")
    git(work, "config", "user.name", "test")
    git(work, "config", "user.email", "test@example.com")
    (work / "scripts").mkdir()
    shutil.copy2(SCRIPT, work / "scripts")
    (work / "reports" / "market").mkdir(parents=True)
    (work / "README.md").write_text("x\n")
    git(work, "add", ".")
    git(work, "commit", "-qm", "init")
    git(work, "push", "-q", "origin", "main")
    return remote, work


def test_publishes_finished_reports_only(repos):
    remote, work = repos
    finished = report(work, FINISHED)
    report(work, UNFINISHED)
    (work / "notes.txt").write_text("staged in the checkout, not a report\n")
    git(work, "add", "notes.txt")
    result = publish(work)
    assert result.returncode == 0, result.stdout + result.stderr
    assert git(remote, "show", "--name-only", "--format=", "main").split() == [finished]
    assert git(work, "diff", "--cached", "--name-only").split() == ["notes.txt"]  # still staged, never committed
    again = publish(work)
    assert (again.returncode, again.stdout.strip()) == (0, "no finished report to publish")
    assert len(subjects(remote)) == 2


def test_failed_push_is_undone_and_retried_on_top_of_merged_work(repos, tmp_path):
    remote, work = repos
    finished = report(work, FINISHED)
    hook = remote / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    assert publish(work).returncode == 1  # push rejected
    assert git(work, "rev-parse", "HEAD") == git(remote, "rev-parse", "main")  # no local commit left
    hook.unlink()
    other = tmp_path / "other"  # meanwhile a pull request lands on main
    git(tmp_path, "clone", "-q", str(remote), str(other))
    (other / "README.md").write_text("merged elsewhere\n")
    git(other, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qam", "merged PR")
    git(other, "push", "-q", "origin", "main")
    result = publish(work)
    assert result.returncode == 0, result.stdout + result.stderr
    assert subjects(remote)[1:] == ["merged PR", "init"]
    assert finished in git(remote, "ls-tree", "-r", "--name-only", "main").split()


def _edit(work: Path) -> None:
    (work / "README.md").write_text("edited in the deployment checkout\n")
    git(work, "commit", "-qam", "not a report")


def _edit_and_revert(work: Path) -> None:
    _edit(work)
    git(work, "revert", "--no-edit", "HEAD")


def _commit_unfinished_report(work: Path) -> None:
    git(work, "add", report(work, UNFINISHED))
    git(work, "commit", "-qm", "today's report, too early")


@pytest.mark.parametrize("local_commit", [_edit, _edit_and_revert, _commit_unfinished_report])
def test_refuses_when_local_main_has_its_own_commits(repos, local_commit):
    remote, work = repos
    report(work, FINISHED)
    local_commit(work)
    assert publish(work).returncode == 1
    assert subjects(remote) == ["init"]
