"""Operator entry point for explicit historical Garmin lap enrichment."""

import argparse
import math
import sys

from app.garmin_client import GarminAuthenticationError
from app.services.split_backfill import (
    SplitBackfillError,
    SplitBackfillProgress,
    SplitBackfillValidationError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.splits_cli")
    commands = parser.add_subparsers(dest="command", required=True)
    backfill = commands.add_parser(
        "backfill",
        help="Fetch Garmin lap elevation for an athlete's entire stored history.",
    )
    backfill.add_argument("--user-id", type=int, required=True)
    backfill.add_argument("--batch-size", type=int, default=100)
    backfill.add_argument("--delay-seconds", type=float, default=1)
    backfill.add_argument("--after-id", type=int, default=0)
    return parser


def _print_progress(progress: SplitBackfillProgress) -> None:
    print(
        f"Processed {progress.processed}; updated {progress.updated}. Resume with --after-id {progress.after_id}.",
        flush=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.user_id < 1 or args.after_id < 0 or not 1 <= args.batch_size <= 1000:
        parser.error(
            "Use a positive user ID, nonnegative cursor, and --batch-size between 1 and 1000."
        )
    if not math.isfinite(args.delay_seconds) or args.delay_seconds < 0:
        parser.error("--delay-seconds must be finite and nonnegative.")

    from app.db import SessionLocal
    from app.garmin_client import GarminApiClient
    from app.security import TokenCipher
    from app.services.cache_invalidator import UserCacheInvalidator
    from app.services.split_backfill import SplitBackfillService
    from app.split_backfill_repository import SplitBackfillRepository

    with SessionLocal() as session:
        service = SplitBackfillService(
            SplitBackfillRepository(session),
            GarminApiClient(),
            TokenCipher(),
            UserCacheInvalidator(),
            on_progress=_print_progress,
        )
        try:
            result = service.run(
                user_id=args.user_id,
                batch_size=args.batch_size,
                delay_seconds=args.delay_seconds,
                after_id=args.after_id,
            )
        except SplitBackfillError as exc:
            print(
                f"Backfill stopped at activity {exc.activity_id}. Resume with --after-id {exc.after_id}.",
                file=sys.stderr,
            )
            # Do not print provider exceptions, which can contain authentication or response material.
            if isinstance(exc.__cause__, SplitBackfillValidationError):
                print(str(exc.__cause__), file=sys.stderr)
            elif isinstance(exc.__cause__, GarminAuthenticationError):
                print("Reconnect Garmin before resuming.", file=sys.stderr)
            return 1
        print("Garmin split backfill complete.")
        _print_progress(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
