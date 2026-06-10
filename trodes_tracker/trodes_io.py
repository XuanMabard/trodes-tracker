"""
trodes_io.py

A thin layer over ``trodesnetwork`` so the rest of the package never touches the
socket API directly. Everything that subscribes to a Trodes channel goes through
here, which keeps the connection details (channel names, server address, message
shape) in one place.
"""

from trodesnetwork.socket import SourceSubscriber

DEFAULT_SERVER = "tcp://127.0.0.1:49152"


# ----------------------------------------------------------------------------
# Subscribing to channels
# ----------------------------------------------------------------------------

def subscribe(channel, server=DEFAULT_SERVER):
    """Return a SourceSubscriber for ``channel`` on the given Trodes server."""
    return SourceSubscriber(channel, server_address=server)


def iter_messages(channel, server=DEFAULT_SERVER):
    """Yield messages from a Trodes channel forever (blocks between samples)."""
    sub = subscribe(channel, server)
    while True:
        yield sub.receive()


def iter_positions(server=DEFAULT_SERVER):
    """Yield raw messages from ``source.position`` (the tracked x/y stream)."""
    return iter_messages("source.position", server)


def iter_events(server=DEFAULT_SERVER):
    """Yield raw messages from ``source.event``."""
    return iter_messages("source.event", server)


# ----------------------------------------------------------------------------
# Pulling x, y out of a Trodes position message (defensive about its shape)
# ----------------------------------------------------------------------------

def extract_xy(msg):
    """Return ``(x, y)`` floats from a position message, or ``None`` if absent."""
    if isinstance(msg, dict):
        for kx, ky in (("x", "y"), ("xloc", "yloc"), ("X", "Y")):
            if kx in msg and ky in msg:
                return float(msg[kx]), float(msg[ky])
        return None
    if isinstance(msg, (bytes, str)):
        text = msg.decode() if isinstance(msg, bytes) else msg
        if "," in text:
            try:
                x, y = text.split(",")[:2]
                return float(x), float(y)
            except ValueError:
                return None
    return None
