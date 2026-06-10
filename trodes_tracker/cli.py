#!/usr/bin/env python3
"""
cli.py

Command-line front-end for the hexagon position tracker. The real work lives in
``trodes_tracker.tracker``; this file only parses arguments and prints errors.

Usage:
    python -m trodes_tracker.cli PATH_TO.trackgeometry --width 640 --height 480

    # or, once installed:
    hex-tracker PATH_TO.trackgeometry -W 640 -H 480

    # custom Trodes server address (default is the local machine):
    hex-tracker maze.trackgeometry -W 640 -H 480 --server tcp://127.0.0.1:49152
"""

import sys
import argparse

from . import tracker
from . import trodes_io


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="hex-tracker",
        description="Report which hexagon the Trodes-tracked position is in, "
                    "in real time.")
    parser.add_argument(
        "geometry",
        help="Path to the .trackgeometry file containing the hexagon zones.")
    parser.add_argument(
        "-W", "--width", type=float, required=True,
        help="Camera width in pixels (Trodes -resolutionx). Required because "
             "the position stream is in pixels.")
    parser.add_argument(
        "-H", "--height", type=float, required=True,
        help="Camera height in pixels (Trodes -resolutiony).")
    parser.add_argument(
        "--server", default=trodes_io.DEFAULT_SERVER,
        help="Trodes network server address (default: %(default)s).")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        tracker.run(args.geometry, args.width, args.height, server=args.server)
    except tracker.GeometryError as exc:
        sys.exit(str(exc))
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
