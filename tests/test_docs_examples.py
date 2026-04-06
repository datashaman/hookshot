"""Load committed example configs under docs/examples through the real config pipeline.

Issue #22: invalid or stale example YAML should fail CI.
"""

from pathlib import Path

from hookshot.config import load_config, validate_config

ROOT = Path(__file__).resolve().parents[1]


def test_docs_example_yml_files_validate():
    examples_dir = ROOT / "docs" / "examples"
    assert examples_dir.is_dir(), "docs/examples must exist (add docs/examples/*.yml)"
    paths = sorted(examples_dir.glob("*.yml"))
    assert paths, "add at least one docs/examples/*.yml for regression coverage"
    for path in paths:
        config = load_config(path)
        errors = validate_config(config)
        assert not errors, f"{path.relative_to(ROOT)}: {errors}"


def test_repo_hookshot_yml_validates():
    """Root example config stays aligned with validate_config (README points here)."""
    path = ROOT / "hookshot.yml"
    assert path.is_file()
    config = load_config(path)
    errors = validate_config(config)
    assert not errors, errors
