import argparse
import logging
import sys
from datetime import date

from connection.db import create_source_sessionmaker, create_target_sessionmaker
from sync.init import run_init

from sync.full_load import run_full_load
from sync.incremental import run_incremental
from sync.validate import run_validate, check_consistency

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("sync")

# Note for Grading: I used generative AI to help me build/debug the CLI pipeline structure.
# On init.py, using AI to learn more about logging lib helped me implement it here.
# However, I also used Generative AI in cli.py to help me implement the argparse structure
# And to review the code implementation overall.


def main() -> int:
    parser = argparse.ArgumentParser(prog="sync")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser("full-load")
    sub.add_parser("incremental")
    validate = sub.add_parser("validate")
    validate.add_argument("--from", dest="date_from")
    validate.add_argument("--to", dest="date_to")
    args = parser.parse_args()

    Source = create_source_sessionmaker()
    Target = create_target_sessionmaker()

    try:
        with Source() as source, Target() as target:
            if args.command == "init":
                run_init(source, target)
            elif args.command == "full-load":
                run_full_load(source, target)
                check_consistency(source, target)
            elif args.command == "incremental":
                run_incremental(source, target)
                check_consistency(source, target)
            elif args.command == "validate":
                date_from = (
                    date.fromisoformat(args.date_from) if args.date_from else None
                )
                date_to = date.fromisoformat(args.date_to) if args.date_to else None
                run_validate(source, target, date_from, date_to)
            else:
                raise NotImplementedError(args.command)
            target.commit()  # 1 transaction per execution
    except Exception as exc:
        log.exception("%s failed", args.command)
        print(f"{args.command} failed: {exc}")
        return 1  # exit code 1/0

    print(f"{args.command} completed successfully")
    return 0  # exit code 1/0


if __name__ == "__main__":
    sys.exit(main())
