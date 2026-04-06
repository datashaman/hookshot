"""JSON-backed state store for cross-event continuity."""

import json
import logging
import os
import tempfile
from pathlib import Path

log = logging.getLogger("hookshot")


class StateStore:
    """Flat key-value store where each key holds a bucket of values and a log."""

    def __init__(self, path: Path):
        self.path = path

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            with open(self.path) as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            log.error("Corrupt state file %s: %s", self.path, e)
            raise
        except (IOError, PermissionError) as e:
            log.error("Cannot read state file %s: %s", self.path, e)
            raise

    def _save(self, data: dict):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, self.path)
        except (IOError, PermissionError) as e:
            log.error("Cannot write state file %s: %s", self.path, e)
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def get(self, key: str) -> dict:
        """Return raw bucket {"values": {...}, "log": [...]} or empty structure."""
        data = self._load()
        return data.get(key, {"values": {}, "log": []})

    def get_context(self, key: str) -> dict:
        """Return a flat dict for template expansion.

        All values are available directly, plus a "context" key
        containing log entries joined with newlines.
        """
        bucket = self.get(key)
        ctx = dict(bucket.get("values", {}))
        ctx["context"] = "\n".join(bucket.get("log", []))
        return ctx

    def store(self, key: str, values: dict | None = None, log_entry: str | None = None):
        """Merge values and/or append a log entry to a bucket."""
        data = self._load()
        bucket = data.setdefault(key, {"values": {}, "log": []})
        bucket.setdefault("values", {})
        bucket.setdefault("log", [])
        if values:
            bucket["values"].update(values)
        if log_entry:
            bucket["log"].append(log_entry)
        self._save(data)
        log.info("  State stored: %s", key)

    def delete(self, pattern: str):
        """Delete keys matching pattern. Supports * suffix for prefix match."""
        data = self._load()
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            keys_to_delete = [k for k in data if k.startswith(prefix)]
        else:
            keys_to_delete = [pattern] if pattern in data else []

        for k in keys_to_delete:
            del data[k]
            log.info("  State cleared: %s", k)

        if keys_to_delete:
            self._save(data)

    def keys(self) -> list[str]:
        """Return all state keys."""
        return list(self._load().keys())
