"""Git worktree management for issue isolation."""

import logging
import subprocess
from pathlib import Path

log = logging.getLogger("hookshot")


def _git_repo_root() -> Path:
    """Return the absolute path to the git repository root."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Not a git repository: {result.stderr.rstrip()}")
    return Path(result.stdout.strip())


def _is_valid_worktree(wt_path: Path) -> bool:
    """Check if a path is a registered git worktree."""
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False

    abs_path = str(wt_path.resolve())
    for line in result.stdout.splitlines():
        if line.startswith("worktree ") and line[9:] == abs_path:
            return True
    return False


def worktree_path(base_path: str, issue_number: int | str) -> Path:
    """Return the deterministic worktree path for an issue.

    If base_path is relative, it is resolved relative to the git repo root.
    """
    path = Path(base_path)
    if not path.is_absolute():
        path = _git_repo_root() / path
    return path / f"issue-{issue_number}"


def ensure_worktree(
    base_path: str,
    issue_number: int | str,
    setup_command: str | None = None,
) -> Path:
    """Create a worktree for the given issue if it doesn't already exist.

    Returns the worktree path.
    Raises RuntimeError if worktree creation or setup fails.
    """
    wt_path = worktree_path(base_path, issue_number)

    if wt_path.exists() and _is_valid_worktree(wt_path):
        log.info("Worktree already exists: %s", wt_path)
        return wt_path

    # Directory exists but is not a valid worktree — clean it up
    if wt_path.exists():
        log.warning("Directory %s exists but is not a valid worktree, removing", wt_path)
        import shutil
        shutil.rmtree(wt_path)

    wt_path.parent.mkdir(parents=True, exist_ok=True)

    branch = f"hookshot/issue-{issue_number}"
    log.info("Creating worktree: %s (branch: %s)", wt_path, branch)

    result = subprocess.run(
        ["git", "worktree", "add", "-b", branch, str(wt_path)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        # Branch may already exist — try without -b
        log.info("Branch %s may already exist, retrying without -b", branch)
        result = subprocess.run(
            ["git", "worktree", "add", str(wt_path), branch],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            log.error("Failed to create worktree: %s", result.stderr.rstrip())
            raise RuntimeError(f"git worktree add failed: {result.stderr.rstrip()}")

    log.info("Worktree created: %s", wt_path)

    if setup_command:
        log.info("Running worktree setup: %s", setup_command)
        setup_result = subprocess.run(
            setup_command,
            shell=True,
            cwd=str(wt_path),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if setup_result.returncode != 0:
            log.error("Worktree setup command failed: %s", setup_result.stderr.rstrip())
            raise RuntimeError(f"Worktree setup failed: {setup_result.stderr.rstrip()}")
        log.info("Worktree setup complete")

    return wt_path


def remove_worktree(
    base_path: str,
    issue_number: int | str,
    teardown_command: str | None = None,
) -> bool:
    """Remove the worktree and its branch for the given issue.

    Returns True if the worktree was removed (or didn't exist).
    """
    wt_path = worktree_path(base_path, issue_number)

    if not wt_path.exists():
        log.info("Worktree does not exist: %s", wt_path)
        return True

    if teardown_command:
        log.info("Running worktree teardown: %s", teardown_command)
        try:
            teardown_result = subprocess.run(
                teardown_command,
                shell=True,
                cwd=str(wt_path),
                capture_output=True,
                text=True,
                timeout=300,
            )
            if teardown_result.returncode != 0:
                log.warning("Worktree teardown command failed: %s", teardown_result.stderr.rstrip())
        except subprocess.TimeoutExpired:
            log.warning("Worktree teardown timed out")

    log.info("Removing worktree: %s", wt_path)
    result = subprocess.run(
        ["git", "worktree", "remove", "--force", str(wt_path)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        log.error("Failed to remove worktree: %s", result.stderr.rstrip())
        return False

    log.info("Worktree removed: %s", wt_path)

    # Clean up the branch
    branch = f"hookshot/issue-{issue_number}"
    log.info("Deleting branch: %s", branch)
    branch_result = subprocess.run(
        ["git", "branch", "-D", branch],
        capture_output=True,
        text=True,
    )
    if branch_result.returncode != 0:
        log.warning("Failed to delete branch %s: %s", branch, branch_result.stderr.rstrip())

    return True


def extract_issue_number(payload: dict) -> int | None:
    """Extract the issue number from a webhook payload, if present."""
    issue = payload.get("issue", {})
    number = issue.get("number")
    if number is not None:
        return int(number)
    return None
