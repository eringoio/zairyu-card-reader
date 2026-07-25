"""Local-only FastAPI host for the standalone residence-card reader."""

from __future__ import annotations

from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from reader.local_api import router as local_router
from reader.local_guard import (
    MAX_REQUEST_BYTES,
    TOKEN_HEADER,
    content_length_is_acceptable,
    host_header_is_local,
    new_request_token,
    request_provenance_is_acceptable,
    token_is_required,
    token_matches,
)
from reader.runtime_paths import static_dir

STATIC_DIR = static_dir()

# Minted once per process. The only way to obtain it is to be served the page by this
# server, over a loopback Host. It is deliberately not exposed by any API, not written to
# a log, and not passed on a command line.
LOCAL_REQUEST_TOKEN = new_request_token()
TOKEN_PLACEHOLDER = "__LOCAL_REQUEST_TOKEN__"

app = FastAPI(title="Zairyu Local Reader")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(local_router)


def _rejection(message: str, status_code: int) -> JSONResponse:
    """A refusal that names no internal detail, path, exception, or card field."""
    return JSONResponse({"success": False, "error_code": "local_request_rejected", "message": message}, status_code=status_code)


@app.middleware("http")
async def enforce_local_request_policy(request: Request, call_next: Any) -> Response:
    """Reject anything that is not this machine's own page talking to this process."""
    if not host_header_is_local(request.headers.get("host")):
        # DNS rebinding and Host-header spoofing both fail here: the header still carries
        # the name the client dialled, which is never a loopback name for a remote page.
        return _rejection("This application accepts local requests only.", 400)

    if not content_length_is_acceptable(request.headers.get("content-length"), limit=MAX_REQUEST_BYTES):
        return _rejection("The request body is too large.", 413)

    if not request_provenance_is_acceptable(
        request.method,
        origin=request.headers.get("origin"),
        referer=request.headers.get("referer"),
        sec_fetch_site=request.headers.get("sec-fetch-site"),
    ):
        return _rejection("This application accepts local requests only.", 403)

    if token_is_required(request.url.path) and not token_matches(request.headers.get(TOKEN_HEADER), LOCAL_REQUEST_TOKEN):
        return _rejection("Reload the local application window and try again.", 403)

    try:
        response = await call_next(request)
    except Exception:
        # Never surface a traceback or exception text: card values, certificate bytes and
        # local paths all routinely appear in them.
        return _rejection("The local request could not be completed.", 500)

    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store"
        # The packaged WebView2 shell loads only this local origin. Keep the
        # browser fallback subject to the same no-remote-resource boundary.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; connect-src 'self'; base-uri 'self'; "
            "form-action 'self'; frame-ancestors 'none'; object-src 'none'"
        )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/")
def index() -> HTMLResponse:
    """Serve the staff page with this process's request token embedded in it.

    Injecting at serve time rather than exposing a "fetch me a token" endpoint matters:
    an endpoint that hands out the token on request would hand it to a rebound origin too.
    """
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html.replace(TOKEN_PLACEHOLDER, LOCAL_REQUEST_TOKEN))


@app.get("/api/health")
def health() -> dict[str, Any]:
    # Keep the existing success/message contract so older local callers continue to
    # work, while allowing the desktop launcher to tell this process apart from an
    # unrelated service that happens to use the same TCP port. This endpoint is token
    # exempt by design and returns no card, reader, or configuration data.
    return {"success": True, "message": "ok", "app": "zairyu-reader"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8787)
