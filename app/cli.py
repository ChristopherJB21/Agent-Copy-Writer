from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import VALID_SLOTS  # noqa: E402
from app.db.connection import close_pool, execute  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="app.cli",
        description="AI Marketing Copilot (Agent Copy Writer) - promo content pipeline.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Create the table schema (idempotent) from app/db/schema.sql")

    seed_parser = sub.add_parser("seed", help="Fill deterministic dummy data")
    seed_parser.add_argument(
        "--force", action="store_true", help="Delete existing data, then reseed"
    )

    trigger_parser = sub.add_parser(
        "trigger", help="Run the copywriter -> reviewer -> delivery pipeline"
    )
    trigger_parser.add_argument(
        "--slot",
        choices=list(VALID_SLOTS),
        default="morning",
        help="Prime-time slot (affects the title label and content nuance)",
    )
    trigger_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the result to the terminal and save outputs/ without sending Telegram",
    )
    return parser


async def _cmd_init_db() -> None:
    schema_path = PROJECT_ROOT / "app" / "db" / "schema.sql"
    sql = schema_path.read_text(encoding="utf-8")
    await execute(sql)
    print(f"[OK] Schema applied from {schema_path.name} (idempotent).")


async def _cmd_seed(force: bool) -> None:
    from tabulate import tabulate

    from app.db.seed import SKU_DEFS, seed

    result = await seed(force=force)
    if result.get("skipped"):
        print(f"[SKIP] {result['reason']} ({result['existing']} SKUs already present).")
        return
    rows = [
        [
            s["sku_code"],
            s["product_name"],
            s["unit_price"],
            f"{s['discount_pct']}%",
            s["stock_qty"],
        ]
        for s in SKU_DEFS
    ]
    print(
        tabulate(
            rows,
            headers=["SKU Code", "Product", "Price", "Discount", "Stock"],
            tablefmt="github",
        )
    )
    print(
        f"[OK] Seed complete: {result['inventory']} SKUs, "
        f"{result['orders']} orders, {result['reviews']} reviews."
    )


async def _cmd_trigger(slot: str, dry_run: bool) -> None:
    from app.agents.pipeline import run_pipeline

    try:
        result = await run_pipeline(slot=slot, dry_run=dry_run)
    except Exception as exc:
        print(f"[ERROR] Pipeline failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(f"\n[OK] Approved={result['approved']} | rounds={result['review_rounds']}")
    print(f"[OK] Delivered: {result['delivered_to']} | archive: {result['output_path']}")

    if dry_run:
        banner = "\u2501" * 60
        print(f"\n{banner}\n{result['message']}\n{banner}")


async def _main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "init-db":
            await _cmd_init_db()
        elif args.command == "seed":
            await _cmd_seed(force=args.force)
        elif args.command == "trigger":
            await _cmd_trigger(slot=args.slot, dry_run=args.dry_run)
        else:
            parser.print_help()
    finally:
        await close_pool()


def main() -> None:
    import selectors

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # pragma: no cover - stream without reconfigure (e.g. test runner)
            pass
    asyncio.run(
        _main(),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
    )


if __name__ == "__main__":
    main()
