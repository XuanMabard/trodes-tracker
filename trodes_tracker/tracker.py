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

from . import geometry
from . import trodes_io


class GeometryError(Exception):
    """Raised when a .trackgeometry file yields no usable zones."""


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

    out("Listening for position. Press Ctrl+C to stop.\n")

    first = True
    last_hex = "uninitialized"

    for msg in trodes_io.iter_positions(server):
        xy = trodes_io.extract_xy(msg)
        if xy is None:
            out(f"Could not read x,y from message: {msg!r}")
            continue
        px, py = xy

        if first:
            first = False
            out("First raw message from Trodes:")
            out(f"    {msg}")
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

        # Print position every sample; flag hexagon changes clearly.
        if hex_id != last_hex:
            out(f"x={px:.2f}  y={py:.2f}   -->   ENTERED {location}")
            last_hex = hex_id
        else:
            out(f"x={px:.2f}  y={py:.2f}   -->   {location}")
