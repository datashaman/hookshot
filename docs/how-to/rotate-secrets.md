# How to rotate webhook secrets

**Goal:** Change the HMAC secret without mystery failures.

## Steps

1. Generate a new random string (long, unguessable).
2. Update the secret wherever GitHub (or `gh webhook forward --secret`) sends deliveries from.
3. Update Hookshot config (or `HOOKSHOT_SECRET`) so the expanded `secret` matches.
4. Restart `hookshot serve` so the process picks up new environment variables if you use `${VAR}` expansion.

## Verify

- Invalid or missing `X-Hub-Signature-256` → **403** and `Invalid signature` body (when a `secret` is configured).
- Health check is unaffected: `GET /` does not require a signature.

## See also

- [Reference: HTTP](../reference/http.md)
