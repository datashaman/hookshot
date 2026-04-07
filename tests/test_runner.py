"""Tests for template expansion, dotpath resolution, and filters."""

from hookshot.runner import apply_filter, expand_template, resolve_dotpath


# --- resolve_dotpath ---


def test_resolve_dotpath_simple():
    assert resolve_dotpath({"a": {"b": "c"}}, "a.b") == "c"


def test_resolve_dotpath_missing_key():
    assert resolve_dotpath({"a": 1}, "b") == ""


def test_resolve_dotpath_none_value():
    assert resolve_dotpath({"a": None}, "a") == ""


def test_resolve_dotpath_bool_true():
    assert resolve_dotpath({"a": True}, "a") == "true"


def test_resolve_dotpath_bool_false():
    assert resolve_dotpath({"a": False}, "a") == "false"


def test_resolve_dotpath_wildcard_extracts_field():
    payload = {
        "issue": {
            "labels": [
                {"name": "bug"},
                {"name": "hookshot"},
                {"name": "enhancement"},
            ]
        }
    }
    result = resolve_dotpath(payload, "issue.labels.*.name")
    assert result == ["bug", "hookshot", "enhancement"]


def test_resolve_dotpath_wildcard_missing_field():
    """Elements missing the requested key are skipped."""
    payload = {
        "items": [
            {"name": "a"},
            {"other": "b"},
            {"name": "c"},
        ]
    }
    result = resolve_dotpath(payload, "items.*.name")
    assert result == ["a", "c"]


def test_resolve_dotpath_wildcard_on_non_list():
    """Wildcard on a non-list value returns empty string."""
    payload = {"a": "string"}
    assert resolve_dotpath(payload, "a.*.name") == ""


def test_resolve_dotpath_wildcard_empty_list():
    payload = {"items": []}
    assert resolve_dotpath(payload, "items.*.name") == []


def test_resolve_dotpath_multiple_wildcards_returns_empty():
    """Multiple wildcards are unsupported and return empty string."""
    payload = {"a": [{"b": [{"c": 1}]}]}
    assert resolve_dotpath(payload, "a.*.b.*.c") == ""


def test_resolve_dotpath_list_without_wildcard_returns_empty():
    """Accessing a field on a list without '*' returns empty string."""
    payload = {"items": [{"name": "a"}, {"name": "b"}]}
    assert resolve_dotpath(payload, "items.name") == ""


# --- apply_filter: existing string filters ---


def test_filter_contains():
    assert apply_filter("hello world", "contains world") == "true"
    assert apply_filter("hello world", "contains xyz") == "false"


def test_filter_not_contains():
    assert apply_filter("hello", "not_contains xyz") == "true"
    assert apply_filter("hello", "not_contains ell") == "false"


def test_filter_eq():
    assert apply_filter("hello", "eq hello") == "true"
    assert apply_filter("hello", "eq HELLO") == "true"
    assert apply_filter("hello", "eq world") == "false"


def test_filter_neq():
    assert apply_filter("hello", "neq world") == "true"
    assert apply_filter("hello", "neq hello") == "false"


def test_filter_lower():
    assert apply_filter("HELLO", "lower") == "hello"


def test_filter_upper():
    assert apply_filter("hello", "upper") == "HELLO"


# --- apply_filter: array filters ---


def test_filter_any_with_list():
    labels = ["bug", "hookshot", "enhancement"]
    assert apply_filter(labels, "any hookshot") == "true"
    assert apply_filter(labels, "any missing") == "false"


def test_filter_any_case_insensitive():
    labels = ["Bug", "Hookshot"]
    assert apply_filter(labels, "any hookshot") == "true"
    assert apply_filter(labels, "any BUG") == "true"


def test_filter_any_with_string_fallback():
    """When value is a string, `any` behaves like `eq`."""
    assert apply_filter("hookshot", "any hookshot") == "true"
    assert apply_filter("hookshot", "any other") == "false"


def test_filter_none_with_list():
    labels = ["bug", "hookshot"]
    assert apply_filter(labels, "none missing") == "true"
    assert apply_filter(labels, "none hookshot") == "false"


def test_filter_none_case_insensitive():
    labels = ["Bug"]
    assert apply_filter(labels, "none bug") == "false"
    assert apply_filter(labels, "none BUG") == "false"


def test_filter_none_with_string_fallback():
    assert apply_filter("hookshot", "none hookshot") == "false"
    assert apply_filter("hookshot", "none other") == "true"


def test_filter_any_empty_list():
    assert apply_filter([], "any hookshot") == "false"


def test_filter_none_empty_list():
    assert apply_filter([], "none hookshot") == "true"


def test_filter_any_with_non_string_elements():
    """any/none coerce non-string elements to strings for comparison."""
    assert apply_filter([42, 0], "any 42") == "true"
    assert apply_filter([42, 0], "any 99") == "false"
    assert apply_filter([True, False], "any true") == "true"


def test_filter_none_with_non_string_elements():
    assert apply_filter([42, 0], "none 42") == "false"
    assert apply_filter([42, 0], "none 99") == "true"


def test_filter_any_empty_arg():
    """any with no arg matches empty-string elements."""
    assert apply_filter(["a", ""], "any") == "true"
    assert apply_filter(["a", "b"], "any") == "false"


def test_filter_none_empty_arg():
    """none with no arg is true when no element is empty string."""
    assert apply_filter(["a", "b"], "none") == "true"
    assert apply_filter(["a", ""], "none") == "false"


# --- expand_template integration ---


def test_expand_template_simple():
    assert expand_template("${{ action }}", {"action": "opened"}) == "opened"


def test_expand_template_with_filter():
    result = expand_template(
        "${{ action | eq opened }}",
        {"action": "opened"},
    )
    assert result == "true"


def test_expand_template_wildcard_with_any():
    payload = {
        "issue": {
            "labels": [
                {"name": "bug"},
                {"name": "hookshot"},
            ]
        }
    }
    result = expand_template(
        "${{ issue.labels.*.name | any hookshot }}",
        payload,
    )
    assert result == "true"


def test_expand_template_wildcard_with_none():
    payload = {
        "issue": {
            "labels": [
                {"name": "bug"},
                {"name": "enhancement"},
            ]
        }
    }
    result = expand_template(
        "${{ issue.labels.*.name | none hookshot }}",
        payload,
    )
    assert result == "true"


def test_expand_template_wildcard_no_filter():
    """Without a filter, a wildcard result is stringified."""
    payload = {"items": [{"x": "a"}, {"x": "b"}]}
    result = expand_template("${{ items.*.x }}", payload)
    assert result == "['a', 'b']"


def test_expand_template_list_with_string_filter():
    """String filters still work on lists via stringification."""
    payload = {"items": [{"x": "hello"}, {"x": "world"}]}
    result = expand_template("${{ items.*.x | contains hello }}", payload)
    assert result == "true"
