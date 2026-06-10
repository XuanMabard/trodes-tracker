"""
tracker.py

The core position-tracking loop: subscribe to the Trodes tracked position,
normalize the pixel coordinates against the camera resolution, and report which
hexagon (zone) the animal is currently inside.

This module knows nothing about argparse or the GUI -- it just takes plain
arguments and writes human-readable lines through an ``out`` callback (defaults
to ``print``), so it can be driven from the CLI, the GUI, or a test.

The position from Trodes ``source.position`` is in PIXELS, so ``width`` and
``height`` must be the camera resolution (Trodes' ``-resolutionx`` /
``-resolutiony``). Incoming pixel coordinates are divided by these to normalize
them into the 0-1 space the ``.trackgeometry`` vertices are stored in.
"""

from datetime import datetime

from . import geometry
from . import trodes_io


class GeometryError(Exception):
    """Raised when a .trackgeometry file yields no usable zones."""


def format_unix_ns(unix_ns):
    """Human-readable local time (to microseconds) for a Unix nanosecond value."""
    return datetime.fromtimestamp(unix_ns / 1e9).strftime("%Y-%m-%d %H:%M:%S.%f")


def run(geometry_path, width, height, server=trodes_io.DEFAULT_SERVER, out=print):
    """Run the position-tracking loop until interrupted.

    Parameters
    ----------
    geometry_path : str   Path to the ``.trackgeometry`` file.
    width, height : float Camera resolution in pixels.
    server : str          Trodes network server address.
    out : callable        Called with each line of human-readable output.
    """
    polygons = geometry.load_polygons(geometry_path)
    if not polygons:
        raise GeometryError(
            f"No zones found in {geometry_path!r}. Check the file path.")

    out(f"Loaded {len(polygons)} hexagons "
        f"(zone ids {min(polygons)}-{max(polygons)}) from {geometry_path}")
    out(f"Camera resolution: {width:.0f} x {height:.0f} pixels")

    out(f"Connecting to Trodes at {server} on 'source.position' ...")
    out("(If this hangs on 'not available yet', the Camera Module isn't "
        "publishing position -- open it and press Track.)\n")

    out("Listening for position. Press Ctrl+C to stop.")
    out("Each line: sample=<MCU count>  recv=<client wall-clock> | x y --> hexagon")
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
        # provides it (recording-computer time), else this client's receive time.
        # Either way it is downstream of the MCU; only `sample` is MCU time.
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
            # Sanity check: pixel coords should fall within the given resolution.
            if px > width or py > height:
                out(f"\n   >>> WARNING: position ({px:.0f}, {py:.0f}) exceeds the")
                out(f"   >>> resolution you gave ({width:.0f} x {height:.0f}).")
                out("   >>> Double-check --width / --height match your camera.\n")
            else:
                out("   (position fits inside the given resolution -- good)\n")

        x_norm = px / width
        y_norm = py / height

        hex_id = geometry.which_hexagon(polygons, x_norm, y_norm)
        location = (f"hexagon {hex_id}" if hex_id is not None
                    else "outside all hexagons")

        # Lead with the MCU sample count (the sync key with neural data), then a
        # client/recording-computer wall-clock for human reading -- clearly NOT
        # MCU time.
        sample_str = sample if sample is not None else "?"
        prefix = (f"sample={sample_str}  "
                  f"{wall_label}={format_unix_ns(wall_ns)} (unix_ns={wall_ns})")

        # Print position every sample; flag hexagon changes clearly.
        if hex_id != last_hex:
            out(f"{prefix} | x={px:.2f} y={py:.2f}   -->   ENTERED {location}")
            last_hex = hex_id
        else:
            out(f"{prefix} | x={px:.2f} y={py:.2f}   -->   {location}")
