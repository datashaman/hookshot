"""Tests for the state store."""

from hookshot.state import MAX_CONTEXT_LENGTH, MAX_LOG_ENTRY_LENGTH, StateStore


def test_load_returns_empty_on_corrupt_json(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text("{invalid json!!")

    store = StateStore(state_file)
    bucket = store.get("any-key")

    assert bucket == {"values": {}, "log": []}
    # Corrupt file should be renamed aside
    backups = list(tmp_path.glob("state.corrupt.*"))
    assert len(backups) == 1


def test_load_returns_empty_on_missing_file(tmp_path):
    state_file = tmp_path / "state.json"
    store = StateStore(state_file)
    assert store.get("any-key") == {"values": {}, "log": []}


def test_store_and_retrieve(tmp_path):
    state_file = tmp_path / "state.json"
    store = StateStore(state_file)

    store.store("k1", values={"a": "1"}, log_entry="first")
    bucket = store.get("k1")
    assert bucket["values"]["a"] == "1"
    assert bucket["log"] == ["first"]


def test_store_merges_values(tmp_path):
    state_file = tmp_path / "state.json"
    store = StateStore(state_file)

    store.store("k1", values={"a": "1"})
    store.store("k1", values={"b": "2"})
    bucket = store.get("k1")
    assert bucket["values"] == {"a": "1", "b": "2"}


def test_delete_key(tmp_path):
    state_file = tmp_path / "state.json"
    store = StateStore(state_file)

    store.store("k1", values={"a": "1"})
    store.delete("k1")
    assert store.get("k1") == {"values": {}, "log": []}


def test_delete_wildcard(tmp_path):
    state_file = tmp_path / "state.json"
    store = StateStore(state_file)

    store.store("prefix:a", values={"x": "1"})
    store.store("prefix:b", values={"y": "2"})
    store.store("other:c", values={"z": "3"})

    store.delete("prefix:*")
    assert store.keys() == ["other:c"]


def test_store_survives_corrupt_then_writes(tmp_path):
    """After loading corrupt state, new writes should succeed."""
    state_file = tmp_path / "state.json"
    state_file.write_text("not json")

    store = StateStore(state_file)
    store.store("k1", values={"a": "1"})

    # Re-read from disk
    store2 = StateStore(state_file)
    bucket = store2.get("k1")
    assert bucket["values"]["a"] == "1"


def test_store_truncates_long_log_entry(tmp_path):
    state_file = tmp_path / "state.json"
    store = StateStore(state_file)

    long_entry = "x" * (MAX_LOG_ENTRY_LENGTH + 100)
    store.store("k1", log_entry=long_entry)
    bucket = store.get("k1")
    assert len(bucket["log"][0]) == MAX_LOG_ENTRY_LENGTH + 1  # +1 for "…"
    assert bucket["log"][0].endswith("…")


def test_get_context_truncates_to_max_length(tmp_path):
    state_file = tmp_path / "state.json"
    store = StateStore(state_file)

    # Store many entries that together exceed MAX_CONTEXT_LENGTH
    for i in range(100):
        store.store("k1", log_entry=f"entry-{i}: " + "a" * 100)

    ctx = store.get_context("k1")
    assert len(ctx["context"]) <= MAX_CONTEXT_LENGTH


def test_get_context_keeps_newest_entries(tmp_path):
    state_file = tmp_path / "state.json"
    store = StateStore(state_file)

    # Store entries where total exceeds limit
    for i in range(100):
        store.store("k1", log_entry=f"entry-{i}: " + "a" * 100)

    ctx = store.get_context("k1")
    # The newest entries should be present, oldest dropped
    assert "entry-99" in ctx["context"]
    assert "entry-0" not in ctx["context"]
