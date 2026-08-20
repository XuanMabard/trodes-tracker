#!/usr/bin/env python3
"""
events.py

Listener for the Trodes event bus -- the "zone detection happens in Trodes"
mode. Zones drawn in the Trodes Camera Module fire named events when the
tracked animal crosses them; this module subscribes to the event channel
(default ``trodes.event``) and reports every event as it arrives, using the
same timestamp conventions as the position tracker. No geometry file and no
local point-in-polygon math are involved -- Trodes does the zone detection.

Like ``tracker.py``, this module knows nothing about argparse or the GUI in
its core loop: ``run()`` takes plain arguments and writes human-readable lines
through an ``out`` callback (defaults to ``print``), so it can be driven from
the CLI, the GUI, or a test.

Usage:
    python -m trodes_tracker.events
    trodes-events --server tcp://127.0.0.1:49152

    # if events never arrive, your Trodes build may publish elsewhere:
    trodes-events --channel trodes.events
"""

import argparse

from . import trodes_io


def run(server=trodes_io.DEFAULT_SERVER,
        channel=trodes_io.DEFAULT_EVENT_CHANNEL, out=print):
    """Listen to the Trodes event bus and report each event until interrupted.

    Parameters
    ----------
    server : str    Trodes network server address.
    channel : str   Event channel to subscribe to (default ``trodes.event``).
    out : callable  Called with each line of human-readable output.
    """
    out(f"Connecting to Trodes at {server} on '{channel}' ...")
    out("(If this hangs on 'not available yet', nothing is publishing the "
        "event bus -- make sure Trodes is running and the Camera Module has "
        "zones configured so zone events fire. If it connects but nothing "
        "ever prints, try --channel trodes.events.)\n")

    out("Listening for ALL events on the bus. Press Ctrl+C to stop.")
    out("Each line: sample=<MCU count>  tsys=<wall-clock> | event: <name>")
    out("  sample : the MCU hardware sample count (Trodes 'localTimestamp').")
    out("           The MCU stamps this SAME counter onto the neural streams,")
    out("           so it is the time that comes from the MCU and the real key")
    out("           for aligning events with neural activity.")
    out("  tsys   : Trodes' 'systemTimestamp' -- the recording computer's")
    out("           wall-clock (Unix ns), downstream of the MCU. Falls back to")
    out("           recv (this client's clock) if absent. Human reading only.\n")

    first = True

    for msg in trodes_io.iter_events(server, channel):
        # Stamp the receive instant immediately, before any work, so the
        # fallback Unix time is as close as possible to acquisition.
        recv_ns = trodes_io.now_unix_ns()

        name = trodes_io.extract_event_name(msg)
        sample = trodes_io.extract_sample_count(msg)
        sys_ns = trodes_io.extract_system_time_ns(msg)
        # Wall-clock for the line: prefer Trodes' systemTimestamp (recording-
        # computer time), else this client's receive time. Either way it is
        # downstream of the MCU; only `sample` is MCU time.
        if sys_ns is not None:
            wall_ns, wall_label = sys_ns, "tsys"
        else:
            wall_ns, wall_label = recv_ns, "recv"

        if first:
            first = False
            out("First raw message from Trodes:")
            out(f"    {msg}")
            if sample is not None:
                out("   MCU time: 'localTimestamp' (hardware sample count) -- "
                    "the shared clock with the neural stream; synchronize on "
                    "this.")
            else:
                out("   >>> WARNING: no MCU sample count ('localTimestamp') in "
                    "the message; neural alignment via sample count is "
                    "unavailable.")
            if sys_ns is not None:
                out("   Wall-clock: Trodes 'systemTimestamp' (tsys) -- the "
                    "recording computer's processing time, downstream of the "
                    "MCU.")
            else:
                out("   Wall-clock: client receive time (recv, time.time_ns) "
                    "-- NOT MCU time; downstream by network + processing "
                    "latency.")
            if name is None:
                out("\n   >>> WARNING: the message has no 'name' field -- this")
                out("   >>> may not be the event channel your Trodes build")
                out("   >>> uses. Try --channel trodes.events.\n")
            else:
                out("   (message carries an event name -- good)\n")

        sample_str = sample if sample is not None else "?"
        wall_str = trodes_io.format_unix_ns(wall_ns)
        prefix = (f"sample={sample_str}  "
                  f"{wall_label}={wall_str} (unix_ns={wall_ns})")

        if name is not None:
            out(f"{prefix} | event: {name}")
        else:
            out(f"{prefix} | event with no 'name': {msg!r}")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="trodes-events",
        description="Print every Trodes event (e.g. Camera Module zone "
                    "crossings) in real time. Zone detection happens inside "
                    "Trodes; this tool just listens.")
    parser.add_argument(
        "--server", default=trodes_io.DEFAULT_SERVER,
        help="Trodes network server address (default: %(default)s).")
    parser.add_argument(
        "--channel", default=trodes_io.DEFAULT_EVENT_CHANNEL,
        help="Trodes channel to subscribe to (default: %(default)s). Escape "
             "hatch in case your Trodes build publishes events elsewhere, "
             "e.g. 'trodes.events'.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        run(server=args.server, channel=args.channel)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
