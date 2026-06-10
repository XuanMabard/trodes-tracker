#!/usr/bin/env python3
"""
events.py

Standalone listener for the Trodes ``source.event`` channel: prints each event's
name and local timestamp as it arrives. This is independent of position tracking
-- it's the "what just happened" feed rather than the "where is the animal" feed.

Usage:
    python -m trodes_tracker.events
    trodes-events --server tcp://127.0.0.1:49152
"""

import argparse

from . import trodes_io


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="trodes-events",
        description="Print Trodes events (source.event) in real time.")
    parser.add_argument(
        "--server", default=trodes_io.DEFAULT_SERVER,
        help="Trodes network server address (default: %(default)s).")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    print("Listening for events... (press Ctrl+C to stop)")
    try:
        for event in trodes_io.iter_events(args.server):
            print("Event:", event["name"], "at timestamp", event["localTimestamp"])
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
