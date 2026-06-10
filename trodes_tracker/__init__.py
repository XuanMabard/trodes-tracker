"""
trodes_tracker
==============

Real-time tools for reading the Trodes network during behavioral experiments.

Modules
-------
geometry   Parse ``.trackgeometry`` files and do point-in-polygon (hexagon) tests.
trodes_io  Thin wrappers over ``trodesnetwork`` (position + event streams).
tracker    Core position-tracking loop (where is the animal, which hexagon).
cli        Command-line front-end for the position tracker.
events     Standalone listener for the Trodes ``source.event`` channel.
gui        Tkinter desktop front-end that drives the position tracker.

Entry points (installed as console scripts via pyproject.toml)
--------------------------------------------------------------
hex-tracker       -> trodes_tracker.cli:main
hex-tracker-gui   -> trodes_tracker.gui:main
trodes-events     -> trodes_tracker.events:main

Or, without installing, from the project root:
    python -m trodes_tracker          # launches the GUI
    python -m trodes_tracker.cli ...  # the position tracker
    python -m trodes_tracker.events   # the event listener
"""

__version__ = "0.1.0"

__all__ = ["geometry", "trodes_io", "tracker", "cli", "events", "gui"]
