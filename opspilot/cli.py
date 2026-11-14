"""Command-line interface for OpsPilot."""

import argparse
import json
import sys
from dataclasses import asdict

from opspilot.monitor import check_endpoint, load_checks


def _format_table(results):
    rows = [
        ("NAME", "STATUS", "LATENCY", "URL"),
        *[
            (
                result.name,
                str(result.status_code) if result.status_code is not None else "ERROR",
                f"{result.latency_ms:.1f} ms",
                result.url,
            )
            for result in results
        ],
    ]
    widths = [max(len(row[column]) for row in rows) for column in range(4)]
    lines = [
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        for row in rows
    ]
    lines.insert(1, "  ".join("-" * width for width in widths))
    for result in results:
        if result.error:
            lines.append(f"  {result.name}: {result.error}")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Check the health of configured HTTP endpoints."
    )
    parser.add_argument(
        "--config",
        default="opspilot.json",
        help="path to JSON config (default: opspilot.json)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print results as JSON",
    )
    args = parser.parse_args(argv)

    try:
        checks = load_checks(args.config)
    except ValueError as error:
        print(f"opspilot: {error}", file=sys.stderr)
        return 2

    results = [check_endpoint(check) for check in checks]
    healthy = all(result.healthy for result in results)
    if args.json:
        print(
            json.dumps(
                {
                    "healthy": healthy,
                    "results": [asdict(result) for result in results],
                },
                indent=2,
            )
        )
    else:
        print(_format_table(results))
        print(f"\nOverall: {'HEALTHY' if healthy else 'UNHEALTHY'}")
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
