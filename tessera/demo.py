"""`python3 -m tessera.demo` — one command, both halves, a working link.

The engine and the console live in two repositories. Asking a reviewer to start
one, clone the other, serve it, read a token out of a terminal and paste a URL
with two query parameters is how a demonstration gets abandoned at step three.

This starts the API, serves the console directory, and prints one link that works.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import pathlib
import socket
import sys
import threading


def free_port(preferred: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            probe.bind(("127.0.0.1", 0))
            return probe.getsockname()[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m tessera.demo",
        description="Serve the API and the console together, and print one link.")
    parser.add_argument("--console", default="../tessera-app",
                        help="path to the console repository (default: ../tessera-app)")
    parser.add_argument("--api-port", type=int, default=8081)
    parser.add_argument("--console-port", type=int, default=8080,
                        help="8080 is on the CORS allowlist by default")
    parser.add_argument("--token", default="demo-token")
    parser.add_argument("--standalone", action="store_true",
                        help="no external CRM: the native store is the system of record")
    parser.add_argument("--tenants", type=int, default=1,
                        help="how many isolated tenants to run in this process (default 1)")
    args = parser.parse_args(argv)

    console = pathlib.Path(args.console).expanduser().resolve()
    if not (console / "index.html").exists():
        print(f"No index.html in {console}.", file=sys.stderr)
        print("Point --console at the tessera-app checkout.", file=sys.stderr)
        return 2

    from . import api as api_module

    if args.tenants > 1:
        from .tenants import multi_tenant_api
        ids = [f"018f0000-0000-7000-8000-{index:012d}" for index in range(1, args.tenants + 1)]
        tokens = {f"{args.token}-{index}": (tenant, api_module.Principal(
            f"p{index}", ("admin",), role="admin"))
            for index, tenant in enumerate(ids, start=1)}
        service = multi_tenant_api(
            ids, tokens,
            lambda tenant, tenant_tokens: api_module.demo_api(
                tenant_id=tenant, token=tenant_tokens[0], standalone=args.standalone))
        print(f"  Tenants   {args.tenants} isolated", flush=True)
        first_token = list(tokens)[0]
        for token, (tenant, _principal) in tokens.items():
            print(f"            {tenant[-4:]}  token {token}", flush=True)
    else:
        service = api_module.demo_api(token=args.token, standalone=args.standalone)
    api_port = free_port(args.api_port)
    console_port = free_port(args.console_port)

    # The console gets whatever port was free, and the engine's allowlist has to
    # know about it. A demo that picks a random port and then refuses the browser
    # on that port is a demo that fails at step four.
    service.allowed_origins = (
        f"http://127.0.0.1:{console_port}", f"http://localhost:{console_port}",
    ) + api_module.DEFAULT_ALLOWED_ORIGINS

    api_server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", api_port), api_module.handler_for(service))
    api_server.daemon_threads = True
    threading.Thread(target=api_server.serve_forever, daemon=True).start()

    static = http.server.ThreadingHTTPServer(
        ("127.0.0.1", console_port),
        functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(console)))
    static.daemon_threads = True
    threading.Thread(target=static.serve_forever, daemon=True).start()

    # In multi-tenant mode each tenant has its own token, and a link that used
    # the single-tenant token would 401 - the sort of detail that makes a demo
    # look broken on the one screen somebody tries first.
    console_token = args.token if args.tenants == 1 else list(tokens)[0]
    link = (f"http://127.0.0.1:{console_port}/index.html"
            f"?engine=http://127.0.0.1:{api_port}&token={console_token}")
    mode = "standalone — the native store is the system of record" if args.standalone \
        else "federated — three simulated systems of record"
    print(f"  Mode      {mode}", flush=True)
    print(f"  API       http://127.0.0.1:{api_port}   token {args.token}", flush=True)
    print(f"  Console   http://127.0.0.1:{console_port}", flush=True)
    print(f"  Open      {link}", flush=True)
    print("\n  Ctrl-C to stop.", flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\n  stopped")
    finally:
        api_server.shutdown()
        static.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
