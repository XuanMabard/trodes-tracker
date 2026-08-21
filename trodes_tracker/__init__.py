"""
trodes_tracker
==============

Real-time tools for reading the Trodes network during behavioral experiments.

Three operating modes
---------------------
Position tracker  Subscribe to ``source.position`` and do zone detection
                  locally with shapely against a ``.trackgeometry`` file.
Hex centroid      Subscribe to ``source.position`` and assign the animal to
                  the hex with the nearest centroid (from a ``hex,x,y`` CSV
                  in raw pixels), with a pixel distance threshold for
                  "outside".
Trodes events     Just listen to the Trodes event bus (``trodes.event``);
                  zone detection happens inside the Trodes Camera Module,
                  whose zones fire named events when crossed.

Modules
-------
geometry   Parse ``.trackgeometry`` files and do point-in-polygon (hexagon) tests.
trodes_io  Thin wrappers over ``trodesnetwork`` (position + event streams).
tracker    Core position-tracking loop (where is the animal, which hexagon).
cli        Command-line front-end for the position tracker.
centroid   Nearest-centroid hex assignment (CSV loading + streaming loop + CLI).
events     Listener for the Trodes event bus (zone detection in Trodes).
gui        Tkinter desktop front-end that drives any of the modes.

Entry points (installed as console scripts via pyproject.toml)
--------------------------------------------------------------
hex-tracker       -> trodes_tracker.cli:main
hex-centroid      -> trodes_tracker.centroid:main
hex-tracker-gui   -> trodes_tracker.gui:main
trodes-events     -> trodes_tracker.events:main

Or, without installing, from the project root:
    python -m trodes_tracker            # launches the GUI
    python -m trodes_tracker.cli ...    # the position tracker
    python -m trodes_tracker.centroid . # the nearest-centroid tracker
    python -m trodes_tracker.events     # the event listener
"""

__version__ = "0.1.0"

__all__ = ["geometry", "trodes_io", "tracker", "cli", "centroid", "events", "gui"]
