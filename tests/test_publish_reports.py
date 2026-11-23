"""scripts/publish_reports.sh against throwaway git repositories. Report contents are SIMULATED."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "publish_reports.sh"
ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}  # never reach the caller's repository
FINISHED, UNFINISHED = "2000-01-01", "2999-01-01"  # before and after any real "today"


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True, env=ENV).stdout


def publish(work: Path) -> subprocess.CompletedProcess:
    return subprocess.run([str(work / "scripts" / "publish_reports.sh")], capture_output=True, text=True, env=ENV)


def report(work: Path, day: str) -> None:
    (work / "reports" / "market" / f"{day}.md").write_text("SIMULATED report\n")


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
    report(work, FINISHED)
    report(work, UNFINISHED)
    (work / "notes.txt").write_text("staged in the checkout, not a report\n")
    git(work, "add", "notes.txt")
    result = publish(work)
    assert result.returncode == 0, result.stdout + result.stderr
    assert git(remote, "show", "--name-only", "--format=", "main").split() == [f"reports/market/{FINISHED}.md"]
    assert publish(work).returncode == 0  # nothing new: a no-op
    assert git(remote, "rev-list", "--count", "main").strip() == "2"


def test_failed_push_is_retried_on_top_of_merged_work(repos, tmp_path):
    remote, work = repos
    report(work, FINISHED)
    remote.rename(tmp_path / "offline.git")
    assert publish(work).returncode != 0  # remote unreachable: the report commit stays local
    (tmp_path / "offline.git").rename(remote)
    other = tmp_path / "other"  # meanwhile a pull request lands on main
    git(tmp_path, "clone", "-q", str(remote), str(other))
    (other / "README.md").write_text("merged elsewhere\n")
    git(other, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qam", "merged PR")
    git(other, "push", "-q", "origin", "main")
    result = publish(work)
    assert result.returncode == 0, result.stdout + result.stderr
    assert git(remote, "log", "--format=%s", "main").splitlines()[1] == "merged PR"
    assert f"reports/market/{FINISHED}.md" in git(remote, "ls-tree", "-r", "--name-only", "main").split()


def test_refuses_to_push_changes_outside_reports(repos):
    remote, work = repos
    (work / "README.md").write_text("edited in the deployment checkout\n")
    git(work, "commit", "-qam", "not a report")
    assert publish(work).returncode == 1
    assert git(remote, "log", "-1", "--format=%s", "main").strip() == "init"
