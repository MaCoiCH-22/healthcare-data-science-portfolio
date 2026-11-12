"""Command line entry point for the synthetic FHIR quality project."""
import argparse
import json
import sqlite3
from pathlib import Path

from src.fhir_quality.fixture import generate
from src.fhir_quality.pipeline import validate_directory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate_args = commands.add_parser("generate", help="Write deterministic synthetic FHIR input")
    generate_args.add_argument("directory", type=Path)
    validate_args = commands.add_parser("validate", help="Build an audit ledger and public summary")
    validate_args.add_argument("source", type=Path)
    validate_args.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "generate":
            generate(args.directory)
            print(f"Created 12 synthetic input batches in {args.directory}")
        else:
            result = validate_directory(args.source, args.output)
            print(json.dumps(result["summary"], indent=2))
    except (ValueError, OSError, sqlite3.Error) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")


if __name__ == "__main__":
    main()
