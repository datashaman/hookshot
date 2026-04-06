"""GitHub emoji reactions to signal agent status."""

from __future__ import annotations

import json
import logging
import subprocess

log = logging.getLogger("hookshot")

# Valid GitHub reaction content types
VALID_REACTIONS = {"+1", "-1", "laugh", "confused", "heart", "hooray", "rocket", "eyes"}


def _reaction_endpoint(payload: dict) -> tuple[str, str] | None:
    """Determine the API endpoint and object node_id for adding reactions.

    Returns (endpoint, node_id) or None if the payload doesn't map to
    a reactable GitHub object.
    """
    repo = payload.get("repository", {}).get("full_name", "")
    if not repo:
        return None

    # Issue comment
    if "comment" in payload and "issue" in payload:
        comment_id = payload["comment"].get("id")
        if comment_id:
            return f"/repos/{repo}/issues/comments/{comment_id}/reactions", str(comment_id)

    # PR review
    if "review" in payload and "pull_request" in payload:
        review_id = payload["review"].get("id")
        pr_number = payload["pull_request"].get("number")
        if review_id and pr_number:
            return f"/repos/{repo}/pulls/{pr_number}/reviews/{review_id}/reactions", str(review_id)

    # Issue or PR (top-level)
    if "issue" in payload:
        number = payload["issue"].get("number")
        if number:
            return f"/repos/{repo}/issues/{number}/reactions", str(number)

    if "pull_request" in payload:
        number = payload["pull_request"].get("number")
        if number:
            return f"/repos/{repo}/issues/{number}/reactions", str(number)

    return None


def add_reaction(payload: dict, content: str) -> bool:
    """Add an emoji reaction to the triggering GitHub object.

    Returns True if the reaction was added successfully.
    """
    if content not in VALID_REACTIONS:
        log.warning("Invalid reaction content: %s", content)
        return False

    result = _reaction_endpoint(payload)
    if result is None:
        log.debug("No reactable object found in payload")
        return False

    endpoint, _ = result

    try:
        proc = subprocess.run(
            ["gh", "api", "-X", "POST", endpoint, "-f", f"content={content}"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            log.warning("Failed to add reaction %s: %s", content, proc.stderr.rstrip())
            return False
        log.info("Added reaction: %s", content)
        return True
    except Exception as e:
        log.warning("Failed to add reaction %s: %s", content, e)
        return False


def remove_reaction(payload: dict, content: str) -> bool:
    """Remove an emoji reaction from the triggering GitHub object.

    Returns True if the reaction was removed successfully.
    """
    if content not in VALID_REACTIONS:
        return False

    result = _reaction_endpoint(payload)
    if result is None:
        return False

    endpoint, _ = result

    # List reactions to find our reaction ID
    try:
        proc = subprocess.run(
            ["gh", "api", endpoint],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            log.warning("Failed to list reactions: %s", proc.stderr.rstrip())
            return False

        reactions = json.loads(proc.stdout)
        # Find the reaction with matching content (prefer our own, but take any)
        for reaction in reactions:
            if reaction.get("content") == content:
                reaction_id = reaction["id"]
                # Delete it — the endpoint for deletion is the parent + /reaction_id
                delete_endpoint = f"{endpoint}/{reaction_id}"
                del_proc = subprocess.run(
                    ["gh", "api", "-X", "DELETE", delete_endpoint],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if del_proc.returncode == 0:
                    log.info("Removed reaction: %s", content)
                    return True
                else:
                    log.warning("Failed to remove reaction %s: %s", content, del_proc.stderr.rstrip())
                    return False

        log.debug("Reaction %s not found to remove", content)
        return False
    except Exception as e:
        log.warning("Failed to remove reaction %s: %s", content, e)
        return False
