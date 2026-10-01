#!/usr/bin/env python3
"""Paper frame budget for iso-3ph.7: the spoke BEACON and a worst-case
declaration, byte-counted in the encodings RFC-075 item 3 and RFC-076 item 5
specify. Result and reading: docs/DESIGN.md section 16.

Run: python tools/frame_budget.py   (stdlib only; asserts its own encoder)
"""
import math
import struct

# SPEC 5.3 deterministic profile. Do not swap in cbor2: it shrinks floats to
# binary16, which the profile bans. Mirrors Valence/tools/valence_probe.py.
def _head(major, v):
    if v <= 23:
        return bytes([major << 5 | v])
    for ai, n in ((24, 1), (25, 2), (26, 4), (27, 8)):
        if v < 1 << (8 * n):
            return bytes([major << 5 | ai]) + v.to_bytes(n, "big")

def u(v): return _head(0, v)
def f32(v): return b"\xfa" + struct.pack(">f", v)
def tstr(s): return _head(3, len(s.encode())) + s.encode()
def arr(xs): return _head(4, len(xs)) + b"".join(xs)
def cmap(pairs):
    assert [k for k, _ in pairs] == sorted(k for k, _ in pairs)
    return _head(5, len(pairs)) + b"".join(u(k) + v for k, v in pairs)

HEADER = 8                 # SPEC 5.1
ESPNOW_V1 = 250            # max_frame_espnow, RFC-075 items 1 and 6
PAYLOAD = ESPNOW_V1 - HEADER
CHUNK = 192                # catalog_chunk_payload, SPEC 8.4
CHUNK_HDR = 14             # BLOB_CHUNK raw header (valence_probe.py)
SAFE = 24                  # RFC-076 item 5: field annotation key, not yet allocated

# RFC-075 item 3: boot_id u32, catalog_etag 8B, flags u8, hub_instance_id u64, wifi_channel u8
beacon = struct.pack("<I8sBQB", 0xFFFFFFFF, b"\xff" * 8, 0x0F, 2**64 - 1, 13)

NAME, FIELD, UNIT = "n" * 32, "k" * 24, "u" * 8   # CDDL maxima: entry name, field name, unit
def entry(rid, cls, direction, access, body_key, body):
    # Appendix C channel-entry; category 7 (auxiliary) per RFC-076 item 5's SHOULD.
    return cmap([(1, u(rid)), (2, tstr(NAME)), (3, u(cls)), (4, u(direction)),
                 (5, u(access)), (6, f32(1000.0)), (7, u(1)), (body_key, body), (10, u(7))])

def readout(rid):          # STATE, one f32 layout field with scale/min/max
    fld = cmap([(1, tstr(FIELD)), (2, u(6)), (3, tstr(UNIT)), (4, f32(0.1)),
                (5, f32(-1e9)), (6, f32(1e9))])
    return entry(rid, 0, 0, 0, 8, arr([fld]))

def actuator(rid):         # INTENT, one float32 schema field with min/max/safe
    fld = cmap([(1, tstr(FIELD)), (2, u(2)), (3, tstr(UNIT)), (5, f32(-1e9)),
                (6, f32(1e9)), (SAFE, f32(0.0))])
    return entry(rid, 2, 1, 1, 9, cmap([(1, fld)]))

def status():              # RFC-078 item 1: {state u8, fault u8, beacon_seq u16} at r=0x01
    flds = [cmap([(1, tstr(n)), (2, u(t)), (3, tstr("")), (4, f32(1.0))])
            for n, t in (("state", 0), ("fault", 0), ("beacon_seq", 2))]
    return cmap([(1, u(1)), (2, tstr("accessory-status")), (3, u(0)), (4, u(0)),
                 (5, u(0)), (6, f32(1.0)), (7, u(1)), (8, arr(flds))])

def declaration(n, shape):  # outer array + status entry + n channel entries, rids from 0x02
    entries = [status()] + [shape(0x02 + i) for i in range(n)]
    return _head(4, len(entries)) + b"".join(entries)

if __name__ == "__main__":
    assert f32(1.0).hex() == "fa3f800000" and tstr("a" * 24)[:2] == b"\x78\x18"
    assert len(beacon) == 22
    print(f"beacon: {HEADER} + {len(beacon)} = {HEADER + len(beacon)} B of {ESPNOW_V1}")
    print(f"BLOB_CHUNK frame: {HEADER} + {CHUNK_HDR} + {CHUNK} = {HEADER + CHUNK_HDR + CHUNK} B")
    for label, shape in (("readout", readout), ("actuator", actuator)):
        print(f"{label} entry (rid>=0x18): {len(shape(0x7F))} B")
    pair = len(readout(0x7F)) + len(actuator(0x7F))
    print(f"mirrored actuator (STATE+INTENT, DESIGN 8): {pair} B")
    print(f"status entry: {len(status())} B")
    for n in (126, 128):
        d = len(declaration(n, actuator))
        print(f"{n} actuators: {d} B ({(d - len(status())) / n:.1f} B/channel), "
              f"{math.ceil(d / CHUNK)} chunks at {CHUNK}, {math.ceil(d / PAYLOAD)} frames at {PAYLOAD}")
    fit = (PAYLOAD - len(status()) - 1) // len(actuator(0x7F))
    print(f"channels in one {PAYLOAD} B payload beside the status entry: {fit}")
