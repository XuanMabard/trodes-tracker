"""
geometry.py

Parse the hexagon zones out of a Trodes ``.trackgeometry`` file and test which
zone a normalized (0-1) point falls in.

This module is pure geometry -- it has no dependency on the Trodes network, so
it is easy to unit-test on its own. The file format handled here is the same one
LorenFrankLab/fsgui's TrackGeometryFileReader reads.
"""

import shapely.geometry


# ----------------------------------------------------------------------------
# 1. Parse the .trackgeometry file -> {zone_id: [(x, y), ...]}
# ----------------------------------------------------------------------------

def parse_zones(path):
    """Read the ``<Zone Objects>`` block into ``{zone_id: [(x, y), ...]}``.

    Inclusion/exclusion blocks are intentionally ignored.
    """
    zones = {}
    with open(path) as f:
        lines = [line.rstrip("\n") for line in f]

    in_zone_section = False
    cur_id = nx = ny = None

    for line in lines:
        s = line.strip()

        # Only read the plain <Zone Objects> block; ignore inclusion/exclusion.
        if s.startswith("<Zone Objects>"):
            in_zone_section = True
            continue
        if s.startswith("<Inclusion") or s.startswith("<Exclusion"):
            in_zone_section = False
            continue
        if not in_zone_section:
            continue

        if s.startswith("Zone id:"):
            cur_id = int(s.split(":")[1].strip())
        elif s.startswith("nodes_x:"):
            nx = [float(v) for v in s.split(":")[1].split()]
        elif s.startswith("nodes_y:"):
            ny = [float(v) for v in s.split(":")[1].split()]
            if cur_id is not None and nx is not None:
                zones[cur_id] = list(zip(nx, ny))
            cur_id = nx = ny = None

    return zones


def build_polygons(zones):
    """Build shapely polygons, kept in normalized 0-1 space."""
    polygons = {}
    for zid, pts in zones.items():
        poly = shapely.geometry.Polygon(pts)
        if not poly.is_valid:
            poly = poly.buffer(0)  # repair minor self-touching rings
        polygons[zid] = poly
    return polygons


def which_hexagon(polygons, x_norm, y_norm):
    """Return the zone id whose polygon contains the point, or None."""
    point = shapely.geometry.Point(x_norm, y_norm)
    for zid, poly in polygons.items():
        if poly.contains(point):
            return zid
    return None


def load_polygons(path):
    """Convenience: parse a ``.trackgeometry`` file straight into polygons.

    Returns ``{}`` if the file contains no zones.
    """
    return build_polygons(parse_zones(path))
