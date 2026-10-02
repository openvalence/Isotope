#!/usr/bin/env python3
"""Paper frame budget (iso-3ph.8): the spoke frames and a worst-case
30-channel accessory declaration, byte-counted in the landed encodings
(Valence 9dd395d: SPEC 13.3.1, 13.3.2, 8.10, Appendix C), then checked
against the hub budgets Nucleus sized for (docs/accessory-store-sizing.md).
Result and reading: docs/DESIGN.md section 16, which quotes this output.

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

# Registry limits (Valence spec/registry/registry.yaml).
HEADER = 8                 # SPEC 5.1
ESPNOW_V1 = 250            # max_frame_espnow; SPEC 13.3.1 item 1
PAYLOAD = ESPNOW_V1 - HEADER
CHUNK = 192                # catalog_chunk_payload, SPEC 8.4
CHUNK_HDR = 14             # BLOB_CHUNK raw header, Valence wire/blob_chunks.hpp
DECL_MAX = 4096            # accessory_declaration_max_bytes, SPEC 8.10
ENTRY_MAX = 4096           # catalog_max_entry_bytes, SPEC 8.1
OWN = 30                   # accessory_slice_ids 0x20 less r=0 and r=1, SPEC 8.10
SAFE, SIZE = 25, 18        # CDDL field keys: safe (RFC-076), size (RFC-037, always emitted)

# Nucleus docs/accessory-store-sizing.md (its home; copied here only to reconcile):
# per-accessory pool budget, 32-bit slot sizes, encoded-catalog budget.
NU_ENTRIES, NU_LAYOUT, NU_SCHEMA, NU_LABELS = 31, 33, 30, 64
NU_SLOT_ENTRY, NU_SLOT_FIELD, NU_SLOT_LABEL = 40, 92, 9
NU_CATALOG_BYTES, NU_SCRATCH_FILL = 5120, 0.8

# SPEC 13.3.1 item 3: boot_id u32, catalog_etag 8B, flags u8, hub_instance_id u64, wifi_channel u8
beacon = struct.pack("<I8sBQB", 0xFFFFFFFF, b"\xff" * 8, 0x0F, 2**64 - 1, 13)
# SPEC 13.3.2: accessory_id u64, proto_ver u8, declaration_etag 8B, deadman_ms u16, flags u8, fw str16, product str16
join_req = struct.pack("<QB8sHB16s16s", 1, 1, b"\0" * 8, 5000, 1, b"\0" * 16, b"\0" * 16)
join_reply = struct.pack("<QQBB", 1, 1, 0, 1)   # hub_instance_id, accessory_id, result, flags

NAME, FIELD, UNIT = "n" * 32, "k" * 24, "u" * 8   # CDDL maxima: entry name, field name, unit
def entry(cid, cls, direction, access, body_key, body):
    # Appendix C channel-entry; category 7 (auxiliary) per SPEC 8.10's SHOULD.
    return cmap([(1, u(cid)), (2, tstr(NAME)), (3, u(cls)), (4, u(direction)),
                 (5, u(access)), (6, f32(1000.0)), (7, u(1)), (body_key, body), (10, u(7))])

def readout(cid):          # STATE, one f32 layout field with scale/min/max
    fld = cmap([(1, tstr(FIELD)), (2, u(6)), (3, tstr(UNIT)), (4, f32(0.1)),
                (5, f32(-1e9)), (6, f32(1e9)), (SIZE, u(4))])
    return entry(cid, 0, 0, 0, 8, arr([fld]))

def actuator(cid):         # INTENT, one float32 schema field with min/max/safe
    fld = cmap([(1, tstr(FIELD)), (2, u(2)), (3, tstr(UNIT)), (5, f32(-1e9)),
                (6, f32(1e9)), (SAFE, f32(0.0))])
    return entry(cid, 2, 1, 1, 9, cmap([(1, fld)]))

def status(cid):           # registry accessory_status at r=0x01: state u8, fault u8, beacon_seq u16
    flds = [cmap([(1, tstr(n)), (2, u(t)), (3, tstr("")), (4, f32(1.0)), (SIZE, u(w))])
            for n, t, w in (("state", 0, 1), ("fault", 0, 1), ("beacon_seq", 2, 2))]
    return cmap([(1, u(cid)), (2, tstr("accessory-status")), (3, u(0)), (4, u(0)),
                 (5, u(0)), (6, f32(1.0)), (7, u(1)), (8, arr(flds))])

def mirrored(n):           # n actuators as STATE readback + INTENT writer, 2 ids each
    return [m for i in range(n) for m in (readout, actuator)]

def declaration(shapes, base=0):   # outer array + status + channels at r=0x02..; base 0 = relative ids
    entries = [status(base + 1)] + [s(base + 2 + i) for i, s in enumerate(shapes)]
    assert len(entries) - 1 <= OWN and all(len(e) <= ENTRY_MAX for e in entries)
    return _head(4, len(entries)) + b"".join(entries)

if __name__ == "__main__":
    assert f32(1.0).hex() == "fa3f800000" and tstr("a" * 24)[:2] == b"\x78\x18"
    assert (len(beacon), len(join_req), len(join_reply)) == (22, 52, 18)
    for name, p in (("BEACON", beacon), ("JOIN_REQ", join_req), ("JOIN_REPLY", join_reply)):
        print(f"{name}: {HEADER} + {len(p)} = {HEADER + len(p)} B of {ESPNOW_V1}")
    print(f"BLOB_CHUNK: {HEADER} + {CHUNK_HDR} + {CHUNK} = {HEADER + CHUNK_HDR + CHUNK} B")
    st, ro, ac = len(status(1)), len(readout(0x1F)), len(actuator(0x1F))
    print(f"entries: status (r=0x01) {st} B; at r>=0x18 readout {ro} B, actuator {ac} B, mirrored pair {ro + ac} B")
    for label, shapes in (("30 actuators", [actuator] * OWN), ("30 readouts", [readout] * OWN),
                          ("15 mirrored pairs", mirrored(OWN // 2))):
        d, h = len(declaration(shapes)), len(declaration(shapes, base=0x8000))
        assert d <= DECL_MAX and h <= NU_CATALOG_BYTES
        print(f"{label}: {d} B, {math.ceil(d / CHUNK)} chunks at {CHUNK}, "
              f"{math.ceil(d / PAYLOAD)} frames at {PAYLOAD}; in the hub catalog {h} B")
    worst = len(declaration([actuator] * OWN))
    fit = (PAYLOAD - 1 - st) // ac
    print(f"one {PAYLOAD} B payload holds the status entry and {fit} worst-case channel; "
          f"one {CHUNK} B chunk holds {(CHUNK - 1) // ac} entry")
    one = len(declaration([actuator]))
    print(f"status + 1 worst-case actuator: {one} B, {math.ceil(one / CHUNK)} chunks at {CHUNK}")
    pools = (NU_ENTRIES * NU_SLOT_ENTRY + (NU_LAYOUT + NU_SCHEMA) * NU_SLOT_FIELD
             + NU_LABELS * NU_SLOT_LABEL)
    scratch = round(NU_CATALOG_BYTES / NU_SCRATCH_FILL)
    print(f"hub PSRAM per accessory (Nucleus budget): pools {pools} B + encode scratch {scratch} B "
          f"= {pools + scratch} B")
    print(f"hub flash per accessory: declaration A/B {2 * DECL_MAX} B at the ceiling, "
          f"{2 * worst} B at the worst case")
