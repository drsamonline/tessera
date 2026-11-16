# 46 - CORS, and the gap it exposed

**Status: Draft**

The API had no CORS story at all. Not a wrong one, none. `docs/27` describes ten routes and a bearer token, and says
nothing about a browser client on another origin, which meant the console could not talk to the engine even in
principle.

## What was added

| Piece | Detail |
|---|---|
| Preflight | `OPTIONS` on any route answers `204` with the CORS headers |
| Allowlist | `Api.allowed_origins`, defaulting to the four local development origins |
| Headers | `Access-Control-Allow-Origin` (echoed, never `*`), `Vary: Origin`, `Authorization` and `Content-Type` allowed, `GET, POST, OPTIONS` |

## Why an allowlist and not a wildcard

The API carries a bearer token in a header. `Access-Control-Allow-Origin: *` combined with
`Access-Control-Allow-Credentials` is the classic way to let any page in a user's browser read a tenant's data. Even
without credentials, a wildcard means a malicious page can replay a token it already has against your API from a
victim's browser.

`test_an_unknown_origin_gets_no_cors_header` asserts that an origin outside the list gets no header at all, and
`test_the_allowlist_is_not_a_wildcard` asserts the list itself cannot become one.

## What is still missing

- **No per-tenant origin configuration.** The list is a class attribute; a deployment changes it in code.
- **No credentials mode.** The API uses an `Authorization` header, not cookies, so `Allow-Credentials` is not sent.
- **No rate limiting on preflight.** A `204` costs almost nothing but it is still unbounded.
- **The console does not use it yet.** The engine can now be called from a browser; the console still reads its
  seeded data. That work is next, and this document exists so the gap is written down rather than
  discovered later.
