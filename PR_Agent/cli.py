import argparse
import asyncio
from pathlib import Path

import uvicorn

from PR_Agent.config import get_settings
from PR_Agent.knowledge import build_knowledge_store
from PR_Agent.worker import run_worker


async def index_document(path: Path, kind: str, title: str) -> None:
    content = await asyncio.to_thread(path.read_text, encoding="utf-8")
    resolved = await asyncio.to_thread(path.resolve)
    store = build_knowledge_store(get_settings())
    await store.upsert(str(resolved), title or path.stem, content, kind)


def main() -> None:
    parser = argparse.ArgumentParser(description="PR_Agent control plane")
    subparsers = parser.add_subparsers(dest="command", required=True)
    serve = subparsers.add_parser("serve", help="Start the HTTP API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", default=8000, type=int)
    serve.add_argument("--reload", action="store_true")
    subparsers.add_parser("worker", help="Start the Kafka review worker")
    index = subparsers.add_parser("index", help="Index an ADR, roadmap, or project document")
    index.add_argument("file", type=Path)
    index.add_argument("--kind", default="documentation")
    index.add_argument("--title", default="")
    args = parser.parse_args()
    if args.command == "serve":
        uvicorn.run("PR_Agent.api:app", host=args.host, port=args.port, reload=args.reload)
    elif args.command == "worker":
        asyncio.run(run_worker())
    else:
        asyncio.run(index_document(args.file, args.kind, args.title))


if __name__ == "__main__":
    main()
