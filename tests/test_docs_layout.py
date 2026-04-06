"""Ensure the Diátaxis docs tree from issue #22 exists (regression guard)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_FILES = [
    "docs/README.md",
    "docs/tutorials/getting-started.md",
    "docs/tutorials/webhook-forward.md",
    "docs/how-to/run-agent-from-hook.md",
    "docs/how-to/gate-on-markers.md",
    "docs/how-to/use-worktrees-per-issue.md",
    "docs/how-to/tune-timeouts.md",
    "docs/how-to/gh-webhook-forward.md",
    "docs/how-to/rotate-secrets.md",
    "docs/how-to/debug-hook-not-firing.md",
    "docs/how-to/inspect-state.md",
    "docs/how-to/concurrent-webhooks.md",
    "docs/reference/defaults.md",
    "docs/reference/configuration.md",
    "docs/reference/cli.md",
    "docs/reference/templates-and-filters.md",
    "docs/reference/events.md",
    "docs/reference/state.md",
    "docs/reference/http.md",
    "docs/reference/reactions.md",
    "docs/reference/worktrees.md",
    "docs/reference/gh-forward-supervisor.md",
    "docs/explanation/architecture.md",
]


def test_diataxis_doc_files_exist():
    missing = [p for p in EXPECTED_FILES if not (ROOT / p).is_file()]
    assert not missing, f"Missing documentation files: {missing}"


def test_readme_points_at_docs_index():
    text = (ROOT / "README.md").read_text()
    assert "docs/README.md" in text
    assert "Diátaxis" in text


def test_readme_does_not_document_agents_key():
    """`agents` YAML blocks are not implemented; avoid claiming they work."""
    text = (ROOT / "README.md").read_text()
    assert "agents:" not in text
