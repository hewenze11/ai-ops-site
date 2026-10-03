"""Entry point: `ai-ops-site` / `python -m ai_ops_site`."""
from __future__ import annotations

import argparse
import os

import uvicorn

from .app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Ops website + membership backend")
    parser.add_argument("--host", default=os.environ.get("AI_OPS_SITE_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("AI_OPS_SITE_PORT", "8090")))
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
