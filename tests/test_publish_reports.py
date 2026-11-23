"""scripts/publish_reports.sh against a throwaway bare remote. Report contents are SIMULATED."""
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "publish_reports.sh"


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout


def test_publishes_finished_days_only(tmp_path):
    remote, work = tmp_path / "remote.git", tmp_path / "work"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
    subprocess.run(["git", "clone", "-q", str(remote), str(work)], check=True, capture_output=True)
    git(work, "symbolic-ref", "HEAD", "refs/heads/main")
    git(work, "config", "user.name", "test")
    git(work, "config", "user.email", "test@example.com")
    (work / "scripts").mkdir()
    shutil.copy2(SCRIPT, work / "scripts")
    (work / "reports" / "market").mkdir(parents=True)
    git(work, "add", ".")
    git(work, "commit", "-qm", "init")
    git(work, "push", "-q", "origin", "main")

    today = datetime.now(UTC).date()
    days = [today - timedelta(days=2), today - timedelta(days=1), today]
    for day in days:
        (work / "reports" / "market" / f"{day}.md").write_text("SIMULATED report\n")
    (work / "notes.txt").write_text("a local file that is not a report\n")
    run = lambda: subprocess.run([str(work / "scripts" / "publish_reports.sh")], capture_output=True, text=True)

    first = run()
    assert first.returncode == 0, first.stdout + first.stderr
    published = git(remote, "ls-tree", "-r", "--name-only", "main").split()
    assert f"reports/market/{days[0]}.md" in published and f"reports/market/{days[1]}.md" in published
    assert f"reports/market/{days[2]}.md" not in published and "notes.txt" not in published
    second = run()
    assert (second.returncode, second.stdout.strip()) == (0, "no finished report to publish")
