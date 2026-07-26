"""Request-level protections for the loopback-only staff API.

Binding to ``127.0.0.1`` keeps other machines out. It does **not** keep a *browser* out:
a web page the staff member happens to visit can point a hostname it controls at
``127.0.0.1`` (DNS rebinding) and then talk to this server as if it were same-origin.
Cross-origin rules do not help once that has happened, and none of these endpoints
authenticate a user, because a card reader has no user to authenticate.

Three independent controls close that gap, in order of strength:

1. ``Host`` allowlisting — after rebinding, the ``Host`` header still carries the
   attacker's hostname, so rejecting anything but a loopback name ends the attack.
2. A per-process request token — minted at import, embedded in the page the server itself
   serves, and required on every staff endpoint. It is never logged, never placed on a
   command line, and never returned by an API.
3. ``Origin`` / ``Sec-Fetch-Site`` provenance checks on state-changing requests.

None of this makes the application "secure" on its own. It makes the loopback boundary
behave the way the rest of the product already assumes it does.
"""

from __future__ import annotations

import secrets

# Loopback names only. A rebinding attacker's Host header is never one of these.
LOOPBACK_HOSTNAMES = frozenset({"127.0.0.1", "localhost", "::1"})

TOKEN_HEADER = "x-local-token"

# The staff UI posts only small configuration and scan requests. 1 MiB is far above the
# largest legitimate body and far below anything worth buffering.
MAX_REQUEST_BYTES = 1024 * 1024

# Endpoints reachable without the token. `/api/health` must stay open because the desktop
# launcher polls it to tell this process apart from an unrelated service on the same port,
# before any page — and therefore any token — exists. It returns no card data.
TOKEN_EXEMPT_PATHS = frozenset({"/api/health"})

STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def new_request_token() -> str:
    """Mint a fresh per-process token. 32 bytes of `secrets` entropy, URL-safe."""
    return secrets.token_urlsafe(32)


def hostname_from_host_header(host_header: str | None) -> str:
    """Extract the bare hostname from a ``Host`` header, dropping any port.

    Handles the bracketed IPv6 form (``[::1]:8787``) as well as ``127.0.0.1:8787``.
    Returns an empty string when the header is missing or unusable, which callers treat
    as a rejection rather than a default-allow.
    """
    if not host_header:
        return ""
    host = host_header.strip()
    if host.startswith("["):
        closing = host.find("]")
        return host[1:closing].lower() if closing > 0 else ""
    # A bare IPv6 address without brackets has several colons; only strip a real port.
    if host.count(":") == 1:
        host = host.split(":", 1)[0]
    return host.lower()


def host_header_is_local(host_header: str | None) -> bool:
    return hostname_from_host_header(host_header) in LOOPBACK_HOSTNAMES


def origin_is_local(origin: str | None) -> bool:
    """Return whether an ``Origin``/``Referer`` value points at this loopback server.

    Only ``http`` on a loopback host is accepted. ``null`` (sandboxed iframe, some
    file:// contexts) is not local.
    """
    if not origin or origin == "null":
        return False
    scheme, separator, remainder = origin.partition("://")
    if not separator or scheme.lower() != "http":
        return False
    authority = remainder.split("/", 1)[0]
    return hostname_from_host_header(authority) in LOOPBACK_HOSTNAMES


def request_provenance_is_acceptable(
    method: str,
    *,
    origin: str | None,
    referer: str | None,
    sec_fetch_site: str | None,
) -> bool:
    """Decide whether a state-changing request plausibly came from this server's own page.

    Read-only methods always pass; they are additionally covered by the ``Host`` check and,
    for staff endpoints, by the token. For a state-changing method:

    - a present ``Origin`` must be loopback — a foreign origin is rejected outright;
    - a browser that sends ``Sec-Fetch-Site`` must report ``same-origin`` or ``none``;
    - a request with neither header is allowed through, because a non-browser local client
      (curl, a test, the launcher) sends neither and the token still applies.
    """
    if method.upper() not in STATE_CHANGING_METHODS:
        return True
    if origin is not None:
        return origin_is_local(origin)
    if sec_fetch_site is not None and sec_fetch_site.lower() not in {"same-origin", "none"}:
        return False
    if referer is not None:
        return origin_is_local(referer)
    return True


def token_is_required(path: str) -> bool:
    """Every staff API needs the token; the launcher's health identity endpoint does not."""
    return path.startswith("/api/") and path not in TOKEN_EXEMPT_PATHS


def token_matches(presented: str | None, expected: str) -> bool:
    """Constant-time comparison, so a wrong token cannot be recovered by timing."""
    if not presented:
        return False
    return secrets.compare_digest(presented, expected)


def content_length_is_acceptable(content_length: str | None, *, limit: int = MAX_REQUEST_BYTES) -> bool:
    """Reject an oversized or unparsable declared body length before reading it."""
    if content_length is None:
        return True
    try:
        declared = int(content_length)
    except ValueError:
        return False
    return 0 <= declared <= limit
