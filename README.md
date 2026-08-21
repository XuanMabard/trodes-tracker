# trodes-tracker

Real-time tools for reading the [Trodes](https://spikegadgets.com/trodes/)
network during behavioral experiments, with three operating modes:

- **Position / hexagon tracking (local zone detection)** — subscribe to the
  tracked animal position (`source.position`), normalize the pixel coordinates
  against the camera resolution, and report which hexagon (zone) of a
  `.trackgeometry` file the animal is in, in real time. Available as a CLI and
  a desktop GUI.
- **Hex assignment by nearest centroid** — subscribe to the same position
  stream, but assign the animal to the hex whose centroid (from a `hex,x,y`
  CSV in raw camera pixels) is closest, with a pixel distance threshold —
  positions farther than the threshold from every centroid report as outside.
- **Trodes events (zone detection in Trodes)** — just listen to the Trodes
  event bus (`trodes.event`). Zone detection happens inside the Trodes Camera
  Module: zones configured there fire named events when the animal crosses
  them, and this listener prints each one as it happens.

In position mode it does **not** use the Trodes `EventHandler`; like
[LorenFrankLab/fsgui](https://github.com/LorenFrankLab/fsgui), it subscribes to
`source.position` directly and does point-in-polygon tests locally with
[shapely](https://shapely.readthedocs.io/). Events mode is the complementary
approach: let Trodes do the zone detection and only subscribe to the resulting
events.

## Layout

```
trodes_tracker/
├── geometry.py    # parse .trackgeometry files + point-in-polygon (hexagon) tests
├── trodes_io.py   # thin wrappers over trodesnetwork (position + event streams)
├── tracker.py     # core position-tracking loop (importable, no CLI/GUI deps)
├── cli.py         # command-line front-end for the tracker
├── centroid.py    # nearest-centroid hex assignment (CSV + loop + CLI)
├── events.py      # trodes.event listener (zone detection in Trodes)
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
`pyzmq`, `msgpack`, and `shapely`, and installs four console scripts:
`hex-tracker`, `hex-centroid`, `hex-tracker-gui`, and `trodes-events`.

## Usage

For **position mode**, the position stream from Trodes is in **pixels**, so you
must pass the camera resolution (Trodes' `-resolutionx` / `-resolutiony`) to
normalize against the 0-1 `.trackgeometry` vertices. **Centroid mode** compares
pixels to pixels directly, so it needs no resolution. **Events mode** needs
neither a file nor the resolution.

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

### Hex centroid tracker (CLI)

The centroid file is a CSV with a header row and one row per hex; `x`,`y` are
**raw camera pixels** (same space as the Trodes position stream):

```
hex,x,y
3,716,90
48,714,163
33,644,200
...
```

The pixel distance threshold is **required** — positions farther than this
from every centroid are reported as outside all hexes:

```bash
hex-centroid hex_coordinates.csv --threshold 40

# custom Trodes server, short flag:
hex-centroid hex_coordinates.csv -t 40 --server tcp://127.0.0.1:49152

# or, without installing, from the project root:
python -m trodes_tracker.centroid hex_coordinates.csv -t 40
```

Each line shows the assigned hex and the distance to its centroid (timestamps
mean the same as in the position tracker above):

```
sample=1000  recv=2026-08-20 15:36:05.534305 (unix_ns=1787249405507957599) | x=707.00 y=395.00   -->   hexagon 29 (dist=12.3px)
sample=1030  recv=2026-08-20 15:36:05.567638 (unix_ns=1787249405541290932) | x=200.00 y=100.00   -->   outside all hexes (nearest hexagon 3 at 516.1px)
```

### Desktop GUI (any mode)

```bash
hex-tracker-gui
# or:  python -m trodes_tracker
```

Pick a mode with the radio buttons at the top — each mode's unused inputs grey
out:

- **Position tracker (local zone detection)** — pick a `.trackgeometry` file,
  enter the camera width/height, and click **Start**.
- **Hex assignment by nearest centroid** — pick the hex centroid CSV, enter
  the distance threshold in pixels, and click **Start**.
- **Trodes events (zone detection in Trodes)** — no inputs needed; just click
  **Start** to stream events.

> If it hangs on "not available yet": in position mode the Camera Module isn't
> publishing position — open it and press **Track**. In events mode nothing is
> publishing the event bus — make sure Trodes is running and the Camera Module
> has zones configured so zone events fire.

### Event listener (zone detection in Trodes)

Configure zones in the Trodes **Camera Module** so they fire named events, then:

```bash
trodes-events
trodes-events --server tcp://127.0.0.1:49152
# or:  python -m trodes_tracker.events
```

Every event on the bus is printed (zone events are recognizable by the names
you gave the zones):

```
sample=48123  tsys=2026-08-20 15:36:05.534305 (unix_ns=1755713765534304784) | event: reward_zone_1
```

- **`sample`** — the event's `localTimestamp`: the same MCU hardware sample
  count described above, i.e. the key for aligning events with neural data.
- **`tsys`** — the event's `systemTimestamp` (the recording computer's
  wall-clock, Unix ns), for human reading only; falls back to `recv` (this
  client's clock) if a message doesn't carry it.

If the listener connects but no events ever arrive, your Trodes build may
publish them on a different channel — try:

```bash
trodes-events --channel trodes.events
```
