from __future__ import annotations

import argparse


def run_server(host: str, port: int) -> int:
    from app.runtime_bootstrap import ensure_ml_runtime

    ensure_ml_runtime()

    import uvicorn

    from app.main import app

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
        log_config=None,
        use_colors=False,
    )
    server = uvicorn.Server(config)
    server.run()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--server", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args, _ = parser.parse_known_args()

    if args.server:
        return run_server(args.host, args.port)

    from app.desktop_launcher import main as desktop_main

    return desktop_main()


if __name__ == "__main__":
    raise SystemExit(main())
