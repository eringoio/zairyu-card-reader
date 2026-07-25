# Local API Contract

- `GET /api/health` — local process health. Returns the compatible `success` and `message` fields plus `"app": "zairyu-reader"`, which the desktop launcher uses to distinguish this local service from an unrelated process on the same port.
- `GET /api/local/status` — app version, local reader config, reader state, optional `?check_card=true` card state only.
- `POST /api/local/config` — `{ "reader_id": 0 }`; no remote settings are accepted.
- `POST /api/local/manual-scan` — `{ "reader_id": 0, "card_number": "AB12345678AJ", "use_mock": false }`.
- `POST /api/local/copy-text` — `{ "cards": [{"card_number":"AB12345678AJ"}] }` returns `{ "success": true, "text": "在留カード番号\\t..." }`.

Only the endpoints listed above are registered. Copy requests reject forbidden or unsupported keys, and display labels are always re-derived by the backend.

`GET /api/readers` and `POST /api/check-card` were removed: they duplicated data
`/api/local/status` already returns, the staff UI never called them, and `check-card` took
an unvalidated query parameter while touching the reader.

## Request requirements

Every request must satisfy all of the following, or it is refused before reaching a handler:

| Requirement | Applies to | On failure |
|---|---|---|
| `Host` is `127.0.0.1`, `localhost` or `::1` (any port) | every path | `400` |
| `X-Local-Token` matches this process's token | `/api/local/*` | `403` |
| `Origin`, if present, is loopback; `Sec-Fetch-Site` is not `cross-site` | `POST`/`PUT`/`PATCH`/`DELETE` | `403` |
| `Content-Length` at most 1 MiB | every path | `413` |

The token is minted per process and embedded in the page served by `GET /`, in
`<meta name="local-request-token">`. No endpoint returns it. `/api/health` is the only
token-exempt API, so the launcher can identify this process before any page — and therefore
any token — exists.

Refusals return `{"success": false, "error_code": "local_request_rejected", "message": ...}`
with a fixed message. No traceback, exception text, path, or card value appears in any error
response. `POST /api/local/manual-scan` additionally refuses a request while another read is
already in progress, with `error_code: "read_already_in_progress"`.

No CORS headers are emitted at all. `/` and `/static/*` carry a same-origin
`Content-Security-Policy` and `Cache-Control: no-store`; every response carries
`X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`.
