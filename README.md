# trodes-tracker

Real-time tools for reading the [Trodes](https://spikegadgets.com/trodes/)
network during behavioral experiments:

- **Position / hexagon tracking** — subscribe to the tracked animal position
  (`source.position`), normalize the pixel coordinates against the camera
  resolution, and report which hexagon (zone) of a `.trackgeometry` file the
  animal is in, in real time. Available as a CLI and a desktop GUI.
- **Event reading** — a standalone listener that prints Trodes events
  (`source.event`) as they happen.

It does **not** use the Trodes `EventHandler` for position; like
[LorenFrankLab/fsgui](https://github.com/LorenFrankLab/fsgui), it subscribes to
`source.position` directly and does point-in-polygon tests locally with
[shapely](https://shapely.readthedocs.io/).

## Layout

```
trodes_tracker/
├── geometry.py    # parse .trackgeometry files + point-in-polygon (hexagon) tests
├── trodes_io.py   # thin wrappers over trodesnetwork (position + event streams)
├── tracker.py     # core position-tracking loop (importable, no CLI/GUI deps)
├── cli.py         # command-line front-end for the tracker
├── events.py      # standalone source.event listener
├── gui.py         # Tkinter desktop front-end that drives the tracker
└── __main__.py    # `python -m trodes_tracker` launches the GUI
environment.yml    # conda environment
pyproject.toml     # package metadata + console entry points
```

The pieces share code rather than duplicating it: both the tracker and the event
listener talk to Trodes through `trodes_io`, the tracker uses `geometry` for the
zone math, and the GUI launches the tracker as a subprocess
(`python -m trodes_tracker.cli`) so it stays responsive and can cleanly stop it.

## Setup

```bash
conda env create -f environment.yml
conda activate trodes-events
```

This does an editable install of the project, which pulls in `trodesnetwork`,
`pyzmq`, `msgpack`, and `shapely`, and installs three console scripts:
`hex-tracker`, `hex-tracker-gui`, and `trodes-events`.

## Usage

The position stream from Trodes is in **pixels**, so you must pass the camera
resolution (Trodes' `-resolutionx` / `-resolutiony`).

### Position / hexagon tracker (CLI)

```bash
hex-tracker PATH_TO.trackgeometry --width 640 --height 480

# custom Trodes server (default is the local machine):
hex-tracker maze.trackgeometry -W 640 -H 480 --server tcp://127.0.0.1:49152
```

Without installing, from the project root:

```bash
python -m trodes_tracker.cli PATH_TO.trackgeometry -W 640 -H 480
```

Each output line leads with the MCU sample count (the synchronization key) and a
client wall-clock:

```
sample=1000  recv=2026-06-10 15:36:05.534305 (unix_ns=1781130965534304784) | x=320.00 y=240.00   -->   hexagon 7
```

- **`sample`** — the **MCU hardware sample count** (`timestamp` in the Trodes
  position message). The MCU stamps this *same* counter onto the neural streams
  (their `localTimestamp`), so equal sample counts mean the same instant. **This
  is the time that comes from the MCU and the correct key for aligning position
  with neural data.** To turn it into seconds you need the acquisition sample
  rate and an anchor from the recording side; the position channel alone does not
  expose a sample-count→Unix mapping.
- **`recv` / `tsys`** (wall-clock) — a convenience timestamp for human reading and
  logging, **not** MCU time. It is `time.time_ns()` captured on this client the
  instant the sample arrives (`recv`), or — only if a given Trodes build puts a
  `systemTimestamp` in the position message — the recording computer's processing
  time (`tsys`). Both are *downstream* of the MCU (network + processing latency),
  so do not use them as the neural-alignment key. The startup banner reports
  which one is in use.

### Position / hexagon tracker (GUI)

```bash
hex-tracker-gui
# or:  python -m trodes_tracker
```

Pick a `.trackgeometry` file, enter the camera width/height, and click **Start**.

> If it hangs on "not available yet", the Trodes Camera Module isn't publishing
> position — open it and press **Track**.

### Event listener

```bash
trodes-events
trodes-events --server tcp://127.0.0.1:49152
# or:  python -m trodes_tracker.events
```
