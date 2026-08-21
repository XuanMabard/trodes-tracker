#!/usr/bin/env python3
"""
centroid.py

Hex assignment by nearest centroid -- the third operating mode. Stream the
Trodes-tracked position exactly like the polygon tracker, but assign the
animal to the hex whose centroid is closest, instead of doing shapely
point-in-polygon tests. A required pixel distance threshold decides when the
animal is "outside" (not near any hex).

The centroid file is a CSV with a header row and one row per hex:

    hex,x,y
    3,716,90
    48,714,163
    ...

x and y are RAW CAMERA PIXELS in the same coordinate space as the Trodes
``source.position`` stream, so this mode needs no camera resolution and does
no normalization.

Like ``tracker.py``, the core loop ``run()`` takes plain arguments and writes
human-readable lines through an ``out`` callback (defaults to ``print``), so
it can be driven from the CLI, the GUI, or a test.

Usage:
    python -m trodes_tracker.centroid HEX_CENTROIDS.csv --threshold 40
    hex-centroid HEX_CENTROIDS.csv -t 40 --server tcp://127.0.0.1:49152
"""

import sys
import csv
import math
import argparse

from . import trodes_io


class CentroidError(Exception):
    """Raised when a centroid CSV yields no usable hex centroids."""


# ----------------------------------------------------------------------------
# Pure helpers (no network) -- easy to test on their own
# ----------------------------------------------------------------------------

def load_centroids(path):
    """Read a ``hex,x,y`` CSV into ``{hex_id: (x, y)}`` (pixel coordinates).

    A header row is optional (a first line whose first field isn't an integer
    is treated as the header). Blank lines are ignored. Raises CentroidError
    on malformed rows.
    """
    centroids = {}
    with open(path, newline="") as f:
        for lineno, row in enumerate(csv.reader(f), start=1):
            if not row or not any(cell.strip() for cell in row):
                continue
            first = row[0].strip()
            try:
                hex_id = int(first)
            except ValueError:
                if lineno == 1:  # header row like "hex,x,y"
                    continue
                raise CentroidError(
                    f"{path}: line {lineno}: expected an integer hex id, "
                    f"got {first!r}")
            if len(row) < 3:
                raise CentroidError(
                    f"{path}: line {lineno}: expected 'hex,x,y', got {row!r}")
            try:
                centroids[hex_id] = (float(row[1]), float(row[2]))
            except ValueError:
                raise CentroidError(
                    f"{path}: line {lineno}: x/y are not numbers: {row!r}")
    return centroids


def nearest_hex(centroids, x, y):
    """Return ``(hex_id, distance)`` for the centroid closest to ``(x, y)``."""
    best_id, best_dist = None, float("inf")
    for hid, (cx, cy) in centroids.items():
        d = math.hypot(x - cx, y - cy)
        if d < best_dist:
            best_id, best_dist = hid, d
    return best_id, best_dist


# ----------------------------------------------------------------------------
# The streaming loop
# ----------------------------------------------------------------------------

def run(centroid_path, threshold, server=trodes_io.DEFAULT_SERVER, out=print):
    """Run the nearest-centroid tracking loop until interrupted.

    Parameters
    ----------
    centroid_path : str   Path to the hex centroid CSV (``hex,x,y`` in pixels).
    threshold : float     Max pixel distance to the nearest centroid; positions
                          farther than this from every centroid are "outside".
    server : str          Trodes network server address.
    out : callable        Called with each line of human-readable output.
    """
    centroids = load_centroids(centroid_path)
    if not centroids:
        raise CentroidError(
            f"No hex centroids found in {centroid_path!r}. Check the file.")
    if threshold <= 0:
        raise CentroidError(f"Threshold must be positive (got {threshold}).")

    out(f"Loaded {len(centroids)} hex centroids "
        f"(hex ids {min(centroids)}-{max(centroids)}) from {centroid_path}")
    out(f"Assignment: nearest centroid within {threshold:g} px; farther "
        "positions report as outside all hexes.")
    out("Centroids are raw camera pixels -- no resolution scaling is applied.")

    out(f"Connecting to Trodes at {server} on 'source.position' ...")
    out("(If this hangs on 'not available yet', the Camera Module isn't "
        "publishing position -- open it and press Track.)\n")

    out("Listening for position. Press Ctrl+C to stop.")
    out("Each line: sample=<MCU count>  recv=<client wall-clock> | x y --> hex")
    out("  sample : the MCU hardware sample count (Trodes 'timestamp'). The MCU")
    out("           stamps this SAME counter onto the neural stream (its")
    out("           'localTimestamp'), so it is the time that comes from the MCU")
    out("           and the real key for aligning position with neural activity.")
    out("  recv   : this client's wall-clock when the sample arrived. NOT the MCU")
    out("           time -- it is downstream by network + processing latency, for")
    out("           human reading/logging only.\n")

    first = True
    last_hex = "uninitialized"

    for msg in trodes_io.iter_positions(server):
        # Stamp the receive instant immediately, before any work, so the
        # fallback Unix time is as close as possible to acquisition.
        recv_ns = trodes_io.now_unix_ns()

        xy = trodes_io.extract_xy(msg)
        if xy is None:
            out(f"Could not read x,y from message: {msg!r}")
            continue
        px, py = xy

        sample = trodes_io.extract_sample_count(msg)
        sys_ns = trodes_io.extract_system_time_ns(msg)
        # Wall-clock for the line: prefer Trodes' systemTimestamp if a build
        # provides it (recording-computer time), else this client's receive
        # time. Either way it is downstream of the MCU; only `sample` is MCU
        # time.
        if sys_ns is not None:
            wall_ns, wall_label = sys_ns, "tsys"
        else:
            wall_ns, wall_label = recv_ns, "recv"

        if first:
            first = False
            out("First raw message from Trodes:")
            out(f"    {msg}")
            if sample is not None:
                out("   MCU time: 'sample' (hardware sample count) -- the shared "
                    "clock with the neural stream; synchronize on this.")
            else:
                out("   >>> WARNING: no MCU sample count ('timestamp') in the "
                    "message; neural alignment via sample count is unavailable.")
            if sys_ns is not None:
                out("   Wall-clock: Trodes 'systemTimestamp' (tsys) -- the "
                    "recording computer's processing time, downstream of the MCU.")
            else:
                out("   Wall-clock: client receive time (recv, time.time_ns) -- "
                    "NOT MCU time; downstream by network + processing latency.")
            if px == 0 and py == 0:
                out("\n   >>> WARNING: position is exactly (0, 0) -- the Camera")
                out("   >>> Module may have no tracking solution (check that")
                out("   >>> Track is on and the LED/tracking settings match).\n")
            else:
                out("")

        hex_id, dist = nearest_hex(centroids, px, py)
        if dist <= threshold:
            current = hex_id
            location = f"hexagon {hex_id} (dist={dist:.1f}px)"
        else:
            current = None
            location = (f"outside all hexes "
                        f"(nearest hexagon {hex_id} at {dist:.1f}px)")

        # Lead with the MCU sample count (the sync key with neural data), then
        # a client/recording-computer wall-clock for human reading.
        sample_str = sample if sample is not None else "?"
        prefix = (f"sample={sample_str}  "
                  f"{wall_label}={trodes_io.format_unix_ns(wall_ns)} "
                  f"(unix_ns={wall_ns})")

        # Print position every sample; flag hex changes clearly.
        if current != last_hex:
            out(f"{prefix} | x={px:.2f} y={py:.2f}   -->   ENTERED {location}")
            last_hex = current
        else:
            out(f"{prefix} | x={px:.2f} y={py:.2f}   -->   {location}")


# ----------------------------------------------------------------------------
# CLI front-end
# ----------------------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="hex-centroid",
        description="Report which hex the Trodes-tracked position is in, by "
                    "nearest centroid, in real time.")
    parser.add_argument(
        "centroids",
        help="Path to the hex centroid CSV (header 'hex,x,y'; x,y in raw "
             "camera pixels).")
    parser.add_argument(
        "-t", "--threshold", type=float, required=True,
        help="Max pixel distance to the nearest centroid; positions farther "
             "than this from every centroid are reported as outside.")
    parser.add_argument(
        "--server", default=trodes_io.DEFAULT_SERVER,
        help="Trodes network server address (default: %(default)s).")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        run(args.centroids, args.threshold, server=args.server)
    except (CentroidError, OSError) as exc:
        sys.exit(str(exc))
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
