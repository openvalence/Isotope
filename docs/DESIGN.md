# Isotope: design

> **Nothing here is built.** Home of Isotope's design rulings (C-1: this is
> that fact's one home). The rulings are the operator's of 2026-09-26 and the
> Valence RFC rulings of 2026-10-01 (§14), now landed in the spec; where this
> document goes beyond them it says "proposal" and the question is in §15.
> Wire truth stays in the Valence repo, read-only from here; every protocol
> claim below cites a SPEC section at Valence 9dd395d. Status and measured
> numbers live on the dev board (`bd`, prefix `iso`).

## 1. What Isotope is

The accessory firmware of the Valence ecosystem. An Isotope device is a
small ESP32-family board driving one accessory (a pump, a
motorized stand) that joins ONE Valence hub (Nucleus) over ESP-NOW,
declares its channels, obeys the hub, and fails safe on its own.

Three artifacts, built in this order and no other:

1. **Config format + generator.** A declarative, ESPHome-shaped config is
   the one home for what an accessory is. The generator turns it into an
   image.
2. **Web flasher.** Config in, flashed board out, from a browser.
3. **Visual builder.** A blueprint-style editor over the config. It emits
   the same config and never has a capability the config lacks.

## 2. What the spec gives an accessory

The 2026-09-26 rulings went to the Valence queue as RFC-075 to RFC-079 and
landed on 2026-10-01 (§14). What Isotope builds against:

| Fact | SPEC |
|---|---|
| The ESP-NOW spoke: a star, accessory to host only, no client session on it, ordinary Valence frames with accessory-relative channel ids | §13.3.1 |
| v1 framing pinned: every spoke frame fits 250 B with its 8-byte header; no §5.6 fragmentation, anything larger moves over the blob verb | §13.3.1 item 1 |
| Unencrypted by ruling (H13), bounded by obligations: the accessory clamps every actuating value, the host never treats accessory telemetry as safety-grade | §13.3.1 item 2 |
| BEACON is a permanent 1 Hz heartbeat with a pinned 22-byte payload | §13.3.1 item 3 |
| Active scan on channels 1 to 13, answered by an out-of-cadence beacon | §13.3.1 item 4 |
| The accessory deadman forces its safe state; only BEACON refreshes it | §13.3.1 item 5 |
| ESTOP from any peer; the host repeats it on the spoke and keeps `estop_latched` set while latched | §13.3.1 item 7, §5.5 |
| Join, declaration fetch and rejoin: JOIN_REQ `0x21`, JOIN_REPLY `0x22` | §13.3.2 |
| The user channel space, 32-id slices, the declaration as a catalog, the `safe` annotation, persistence, capacity | §8.10, §8.8 |
| The catalog grows at runtime in the user space only, without revoking readiness | §8.6 |
| Relationships are hub policy with seven registered maps, stored in a STORE | §8.11 |
| PAUSE and ESTOP reach accessories through the host's interlock | §11.6 |
| The `accessory` and `accessory-host` conformance profiles | §17.1, §17.1.1 |
| Config mode: BLE and USB serial, no WiFi, no softAP, no spoke | §13.4.1 |

**Why an accessory deadman forces a safe state when the hub's does not.**
§11.3's hub-side deadman forces no stop because every motion mode is a
bounded plan that settles by itself (§9.6). A pump told "on" has no plan to
run out of; it stays on. That is the case §11.3 carves out for
hub-autonomous sources (`source.background_run`, default `false` = stop),
and the declared `safe` value is the accessory's equivalent of that default,
fixed at flash time.

## 3. Topology

Hub-and-spoke. ESP-NOW is natively a star; the hub (Nucleus) is the center
and every accessory talks only to it.

- **No accessory talks to Phosphor.** Phosphor stays a single-session client
  of the hub and sees accessory channels as ordinary catalog channels.
- **No accessory talks to another accessory**, and nothing is routed.
- **At most 19 accessories, typical 3.** ESP-IDF: "maximum number of paired
  devices is 20" ([ESP-IDF ESP-NOW, ESP32-C6](https://docs.espressif.com/projects/esp-idf/en/stable/esp32c6/api-reference/network/esp_now.html)),
  and the broadcast entry the beacon needs takes one, so a host addresses at
  most 19 accessories by unicast, fewer if a client binding shares the list
  (SPEC §13.3.1 item 8). The catalog binds first: the Flagship is built for
  6 worst-case accessories (§16).
- **Payload 250 B.** ESP-NOW v2 carries 1,470 B, but a v1 receiver only takes
  v2 packets of 250 B or less (same page). Isotope stays at 250: it is the
  spec floor (§13.1) and keeps mixed-version fleets working.
- **Same channel or nothing.** "The channel must be set as the channel that
  the local device is on" (same page). The hub's radio sits on its router's
  channel (station mode), so accessories follow it (§6).
- **Never with the P4 in softAP mode.** A hub never operates a softAP, in
  any mode, including config mode (SPEC §13.3.1 item 9, §13.4.1).

## 4. The hub beacon

BEACON (`0x17`, raw, header channel `0x0000`) is the accessory's only proof
that its hub is alive, and its discovery signal. The host broadcasts it
every `spoke_beacon_interval_ms` (1000) while the spoke is up, every 500 ms
while a pairing window is open, and once out of cadence in answer to a
DISCOVER_PROBE (§6). Payload as pinned, little-endian and tail-extensible
(SPEC §13.3.1 item 3):

| Field | Bytes | What the accessory does with it |
|---|---|---|
| header (§5.1) | 8 | `seq` is the beacon sequence, compared per §7.3 and reported back as accessory-status `beacon_seq` |
| `boot_id` u32 | 4 | a change means its hub rebooted (§15 Q16) |
| `catalog_etag` | 8 | nothing; it is the §13.7 prefix client peers read |
| `flags` u8 | 1 | registry `beacon_flags`: bit0 `pairing_window_open`, bit1 `datagram_estop`, bit2 `accessory_host`, bit3 `estop_latched`; bits 4-7 zero |
| `hub_instance_id` u64 | 8 | the durable hub id; with the source address, the only test of "my hub" |
| `wifi_channel` u8 | 1 | the primary channel the hub transmits on; a beacon heard leaking from an adjacent channel retunes the accessory to the named one |

30 B on the wire (§16). There is no PAUSE or STOP bit: pause reaches
accessories as commanded safe values through the host's interlock (§9), and
only `estop_latched` is broadcast (RFC-075 ruling, 2026-10-01). A hub's
goodbye is a GOODBYE frame, not a bit (§5).

## 5. The accessory deadman

One clock (SPEC §13.3.1 item 5; RFC-075 ruling, 2026-10-01). The accessory
enters its **safe state** when:

- **no BEACON from its hub** (source address and `hub_instance_id` both
  match) has arrived for its deadman window: `spoke_deadman_ms` (5000), or
  the shorter `deadman_ms` it declares in JOIN_REQ, never below 2 x
  `spoke_beacon_interval_ms` (2 s). **Only BEACON refreshes it**; unicast
  commands do not;
- it receives **any GOODBYE** (`0x11`) from its hub, whatever its code and
  even if the payload fails to decode (a host SHOULD broadcast GOODBYE
  `REBOOTING` or `NORMAL_CLOSURE` before a planned reboot);
- it receives a valid, CRC-checked **ESTOP** frame (§5.5) from any source,
  or a BEACON from its hub with `estop_latched` set;
- it detects a **local fault**.

It is also safe at power-on until its hub commands it, and after every join
until its host commands it (§13.3.2).

- **The safe state holds every actuating field at its declared `safe`
  value** (every value-bearing field of a declared INTENT schema or c2h
  STREAM layout) and abandons any verb in progress. The generator refuses
  an actuator without one; readouts declare none.
- **Safe is sticky.** From deadman, GOODBYE or fault the accessory leaves
  safe only on a fresh actuating command received after a matching BEACON;
  from ESTOP, only after a BEACON with `estop_latched` clear, and then only
  on a fresh command. It never restores its pre-safe values on its own,
  mirroring §6.8: "Motion never restarts because a socket reopened."
- **The door is reported.** Accessory-status `state` names it
  (`safe_joined`, `safe_deadman`, `safe_goodbye`, `safe_estop`,
  `safe_fault`); `safe_estop` is the host's ESTOP acknowledgment
  (§17.1.1).
- **`hold` has no wire form** (§15 Q15). `safe` is a typed value inside the
  field's `min`/`max` (SPEC §8.8), so the config's `safe: hold` for a
  position actuator (§10.2) cannot be declared as written.
- **The false-trip arithmetic, stated so the bench can check it.** Broadcast
  frames get no MAC-layer retries, so beacon loss runs higher than unicast
  loss. With per-beacon loss `p`, five in a row happens roughly `p^5` of the
  time: at 10% loss about once a day of continuous use, at 30% about every
  seven minutes. iso-3ph.1 measures `p`; iso-3ph.3 measures the trip itself.

Loss of the hub and loss of the channel look the same, and they share one
code path: safe, then rescan (§6), which is the boot path.

## 6. Channel follow

The host never changes channel for its accessories; it follows its access
point (SPEC §13.3.1 item 4). At boot and on every deadman fire the accessory
scans channels 1 to 13 (RFC-075 ruling: everywhere; a regional accessory MAY
scan a subset), finds its hub, adds it as a peer on that channel, and sends
JOIN_REQ (§7). A router that changes channel therefore costs one deadman
trip (5 s, safe) plus one scan. The BLE channel hint is NOT built (ruling).

**The scan is active** (RFC-075 ruling, 2026-10-01). On each channel the
accessory broadcasts one DISCOVER_PROBE (`0x1E`, the §13.8 payload
unchanged) and listens `spoke_scan_dwell_ms` (150) for a BEACON from its hub
or, in pairing state, any BEACON with `accessory_host` and
`pairing_window_open` set. The host answers a probe with an immediate,
out-of-cadence **broadcast** BEACON, at most one per 150 ms (broadcast,
because a unicast answer to an unknown address would spend a peer-list
entry). 13 x 150 ms is about 2 s cold. Passive listening is also conformant
but needs about 1 s of dwell per channel at a 1 Hz beacon, about 13 s cold.
The probe only finds the hub; the beacon alone feeds the deadman (§5).
iso-3ph.2 measures both forms.

**No spoke in config mode.** A hub in config mode does not run the spoke:
accessory pairing waits until it has joined WiFi, because the spoke follows
the access point's channel and there is none (SPEC §13.4.1; RFC-079 ruling,
2026-10-01).

## 7. Join and pairing

Per SPEC §13.3.2 (RFC-076, ruled 2026-10-01). Lineage: §12.3(c)
push-to-pair.

1. **The hub opens a window**: its pairing control, or the `accessory-admin`
   `window_open` op from a `configure` session (the in-band twin). One
   window, one timer (`pairing_window_default_s`), reported by BEACON
   `pairing_window_open`. **An accepted join is the window's single grant**:
   one press, one device.
2. **The accessory is in pairing state**: by its own local gesture (config
   `pairing`), or on its own when factory-fresh.
3. **It finds a hub** (§6) whose BEACON has `accessory_host` and
   `pairing_window_open` set and sends **JOIN_REQ** (`0x21`, unicast) to that
   beacon's source, once per BEACON received, until answered:
   `accessory_id:u64 + proto_ver:u8 + declaration_etag:8B + deadman_ms:u16 +
   flags:u8 + fw_version:str16 + product:str16` = 52 B, `flags` bit0
   `pairing_state`.
4. **The hub answers JOIN_REPLY** (`0x22`, unicast): `hub_instance_id:u64 +
   accessory_id:u64 + result:u8 + flags:u8` = 18 B, `result` a
   `join_results` value (`accepted`, `window_closed`, `capacity`,
   `unsupported`, `declaration_invalid`, `not_paired`). **Every JOIN_REQ is
   answered**, rate-limited per source for unknown accessories. Flag bit0
   `declaration_needed` makes the reply provisional.
5. **The hub pulls the declaration** (§8): BLOB_REQ `ns = 0`, the accessory
   answers BLOB_CHUNK with §8.4 pacing, the hub verifies SHA-256 against
   `declaration_etag`, sends BLOB_DONE, validates (§8.10) and grows its
   catalog (§8.6); the final JOIN_REPLY follows validation and the capacity
   check. The accessory persists its hub's `hub_instance_id` and address.
6. **Rejoin needs no window.** A paired accessory sends the same JOIN_REQ to
   its stored host on every reacquisition. Equal etag: no transfer.
   Different etag (reflashed, same identity): the host refetches,
   revalidates and replaces the declaration in the same slice, and
   relationships whose target field no longer exists are disabled. A
   forgotten accessory is answered `not_paired` and MAY clear its stored
   hub. After any join the accessory is safe until its host commands it.

**Identity.** `accessory_id` is a u64 the accessory generates randomly at
first boot and persists across reboots and firmware updates; the radio
address is a transport address, not identity. A wiped accessory is a new
one and pairs again (SPEC §8.10).

## 8. Self-description and what the hub stores

**The accessory is self-describing.** Its channels, types, ranges and
deadman are baked in at flash time and declared to its host on join. Only
hub-side things (the accessory's name, relationships) are authored from a
client (SPEC §8.10).

Per channel, the declaration carries: relative id (`0x02`-`0x1F`, 30 at
most), kind (actuator, readout, event, estop button), `packed_field_types`
value type, unit, scale, min/max, `safe` (actuators, REQUIRED), max rate.
Per accessory, JOIN_REQ carries the durable id, product string, firmware
version, deadman and declaration etag (§7).

**One Isotope channel is one catalog entry.** The declaration IS the
accessory's catalog (SPEC §8.10), so a readout is a STATE entry and an
actuator an INTENT entry. Proposal: an actuator also gets a STATE readback
at the next relative id, because a client other than the writer learns an
applied value only from STATE (SPEC §9.3); that spends two ids per actuator,
so a slice holds 15 mirrored actuators. That also matches Phosphor's ruling
that a control is one channel field.

**The declaration is a catalog, not a new grammar** (SPEC §8.10): same CDDL,
same deterministic encoding, same etag, relative ids. It REQUIRES `safe`
(field key 25, §8.8) on every value-bearing field of every INTENT schema and
c2h STREAM layout (`action.*` verbs exempt), SHOULD carry `category`
(`auxiliary`, 7), carries no STORE entries, and its `group` strings are its
own: the host does not rewrite them (RFC-076 ruling). The host validates it
before storing anything: ids in `0x01`-`0x1F`, the `r = 0x01` entry exactly
the registered accessory-status layout, every STATE layout within 242 B,
every INTENT and EVENT worst-case frame within 250 B, every
`setting_channel` inside the declaration, every entry within 4,096 B, the
whole within `accessory_declaration_max_bytes`, every `safe` present and in
range.

**The declaration does not fit one frame.** It is the accessory's blob
namespace 0, pulled by the host with BLOB_REQ and served with §8.4 pacing,
never §5.6 fragmentation (§13.3.1 item 1). Worst case it is 3,592 B in 19
chunks (§16).

**What the hub stores** (SPEC §8.10): `accessory_id`, peer address, slice
index, declaration bytes and etag, `deadman_ms`, the hub-authored name, and
the relationships that reference it. A paired accessory that is absent keeps
its channels in the catalog: offline, shown stale, writes answered NACK
`ACCESSORY_OFFLINE`. Forgetting is host-side only. The accessory stores its
own `accessory_id` and its hub's `hub_instance_id` and address.

**The host proxies, never exposes** (SPEC §17.1.1). It forwards a client
INTENT only after its own checks (tier, declared range, relationship
ownership, the interlock), under its own spoke `intent_id`; the accessory
answers ECHO with its post-clamp applied values, key-complete, or NACK, and
the client's ECHO carries the accessory's values: ground truth. Intents are
absolute (§9.3: "set to 40", never "add 5"). No answer after §13.3's three
retransmits at 100 ms: NACK `ACCESSORY_OFFLINE`.

**Identity is not authenticated** (H13, SPEC §13.3.1 item 2). Any radio in
range can send frames with a paired accessory's address and id. The
obligations that bound it: the accessory clamps every received actuating
value into its declared `min`/`max`, so a forged command does nothing a
legitimate one could not; the host never treats accessory telemetry as
safety-grade input; relationship targets are accessory fields only (§8.11),
so an accessory never drives machine motion; a client never presents spoke
traffic as authenticated. An accessory CAN always stop the machine (an ESTOP
frame from any peer, §13.3.1 item 7), which is the safe direction.

**The accessory channel budget is hub-advertised** (ruled 2026-10-01,
RFC-077; `iso-yg8`). An accessory declares at most 30 own channels; what a
given hub can take is that hub's advertised capacity. The `accessories-roster`
tail carries the per-accessory entry budget (at most 31 entries) and the free
entries, layout fields, schema fields and catalog bytes; a declaration past
either budget is refused JOIN_REPLY `capacity` and reported on
`pairing-events` as `accessory_refused`, never half-admitted (SPEC §8.10).
The reference library's catalog capacities are a hub build parameter
(RFC-077 item 8). The Flagship is built for 6 worst-case accessories, bound
by the 256-entry client floor, not by the radio (Nucleus
`docs/accessory-store-sizing.md`).

**Channel id space** (ruled 2026-10-01, RFC-076). The user space
`0x8000`-`0xBFFF` holds 512 slices of `accessory_slice_ids` (32) ids:
`r = 0x00` is the session-scoped channel BEACON, ACKMASK and GOODBYE ride,
`r = 0x01` the registered accessory-status STATE, `r = 0x02`-`0x1F` the
accessory's own. The accessory uses relative ids and never learns its
slice; a slice is sticky across reboots and declaration replacement and is
never reused after a forget (SPEC §8.10).

## 9. Relationships

Hub policy, evaluated on the accessory host and surviving every client
closing (SPEC §8.11; RFC-078 ruling, 2026-10-01). Isotope never sees one: a
relationship's output reaches it as an ordinary absolute command through
the host's proxy path.

- **Source**: a numeric field of an h2c STATE or STREAM layout anywhere in
  the host's catalog (machine position, speed, another accessory's readout).
  **Target**: a value-bearing field of an accessory INTENT schema or c2h
  STREAM layout. Chains are allowed; a save that would close a feedback loop
  is refused `INVALID_VALUE`.
- **Seven maps** (registry `relationship_maps`), parameters in physical
  units, output finally clamped into the target's `min`/`max`: 1
  `linear_clamp`, 2 `invert`, 3 `threshold_hysteresis`, 4 `slew_limit`, 5
  `lowpass`, 6 `gate` (else the target's `safe`), 7 `piecewise_table`.
- **Evaluated** on every source update, writing only when the output moved
  by the target's `step`, no faster than its `max_rate_hz`; the stateful
  maps also tick at that rate while converging.
- **Stored in the relationships STORE** (`0x0013`, kind `relationship.map`,
  at most `relationships_max` 16, roster `0x0014`) and authored through the
  RFC-067 store verbs on `relationships-write` (`0x0015`, `action.store`),
  the three joined by `store_id` (RFC-070). No relationship-admin channel.
- **Ownership**: an enabled, armed relationship owns its target field; a
  client write to it gets `SOURCE_CONFLICT`.
- **Arming is `resume`** (§11.6). `armed` is volatile and false at every
  boot; saving an enabled relationship arms it at the next `resume`.
- **The interlock** (§11.6): while ESTOP is latched, every relationship is
  disarmed, every target driven to its `safe` value, and client writes to
  actuating accessory fields refused `ESTOP_ACTIVE`. On PAUSE latching, the
  same disarm and drive-to-safe, once; direct client writes under pause stay
  allowed, the operator's own act. This is how pause reaches accessories:
  commanded safe values, not a beacon bit (RFC-075, RFC-085).
- **Degradation**: a removed source or target disables the relationship and
  drives the target to `safe`; an offline target idles it, and on rejoin,
  if still armed, the host sends the current mapped value.
- **Streams**: a c2h bundle is applied on arrival keeping its `t_off`
  offsets; the spoke has no time sync (RFC-078 ruling).

## 10. The config format

Declarative, ESPHome-shaped YAML: device identity, board, radio, pairing,
channels (kind, type, range, safe value, pin binding). One home for what the
accessory is; the declaration's etag is a hash of its channel section. A
sketch, not a schema.

### 10.1 Peristaltic pump (on/off plus 0-100)

```yaml
isotope:
  model: peristaltic-pump
board:
  chip: esp32c3
radio:
  deadman_ms: 5000
pairing:
  button: { pin: 9, inverted: true, hold_ms: 3000 }
status_led: { pin: 8, kind: ws2812 }
channels:
  - key: run
    kind: actuator
    type: bool
    safe: false
    bind: { gpio: 4 }                        # driver enable
  - key: speed
    kind: actuator
    type: u8
    unit: "%"
    range: [0, 100]
    safe: 0
    max_rate_hz: 20
    bind: { pwm: { pin: 5, freq_hz: 20000, min_duty: 12 } }   # below min_duty the motor stalls
```

### 10.2 Motorized stand (machine angle, position with a hold safe state)

```yaml
isotope:
  model: tilt-stand
board:
  chip: esp32c6
channels:
  - key: angle
    kind: actuator
    type: i16
    unit: deg
    scale: 10                                # wire = degrees x 10
    range: [-15.0, 60.0]
    safe: hold                               # stop driving; never seek a "safe" angle
    max_rate_hz: 10
    bind:
      hbridge: { in1: 4, in2: 5, pwm_freq_hz: 20000 }
      feedback: { adc_pin: 1, cal: [[512, -15.0], [3584, 60.0]] }   # two-point pot calibration
      endstops: { min_pin: 6, max_pin: 7 }   # hardware limits cut drive regardless of command
  - key: angle_actual
    kind: readout
    type: i16
    unit: deg
    scale: 10
    range: [-15.0, 60.0]
    max_rate_hz: 5
    bind: { from: angle.feedback }
  - key: moving
    kind: readout
    type: bool
    bind: { from: angle.hbridge }
```

### 10.3 Vibrator

```yaml
isotope:
  model: vibe-bullet
board:
  chip: esp32c3
channels:
  - key: intensity
    kind: actuator
    type: u8
    unit: "%"
    range: [0, 100]
    safe: 0
    max_rate_hz: 50
    bind: { pwm: { pin: 3, freq_hz: 25000, min_duty: 18 } }
  - key: battery
    kind: readout
    type: u8
    unit: "%"
    range: [0, 100]
    max_rate_hz: 0.1
    bind: { adc_pin: 2, divider: 2.0, curve: lipo_1s }
```

Generator refusals (the config's own lint): an actuator with no `safe`;
`hold` on a non-position actuator; a range outside its type; more than 30
channels (15 mirrored actuators); a declaration over
`accessory_declaration_max_bytes` (4,096 B); two channels on one pin.

## 11. Generator and web flasher

**Two shapes, one ruling owed (§15 Q9).**

- *Compiled* (ESPHome's way): the generator emits source and builds a
  per-config image. Unused drivers are not linked; errors surface at build
  time. Needs a toolchain, so the web flasher needs a build server.
- *Prebuilt image plus a config partition* (proposal for v0): one
  application image per chip, and the generator writes the config into its
  own flash partition, parsed at boot. The browser can "generate" with no
  toolchain; the image is tested once per chip, not once per config. Cost:
  every driver ships in every image, and config errors surface at the
  generator's lint rather than the compiler.

Either way the output is an image, per the ruling. **The web flasher** is a
page that flashes over Web Serial (Chromium browsers), the way ESPHome's
[ESP Web Tools](https://esphome.github.io/esp-web-tools/) does. Where the
page lives (this repo, or a Phosphor module) is §15 Q10.

## 12. The visual builder

A blueprint-style editor: pick a board, drop channels, wire them to pins,
set ranges and safe values. It is a front end that reads and writes the
config of §10 and nothing else: the config stays the one home, and a
config written by hand opens in the builder unchanged. Built last.

## 13. Hardware assumptions

**Accessories** are ESP32-family chips with a 2.4 GHz WiFi radio (ESP-NOW
needs one): ESP32, S2, S3, C2, C3, C5, C6, C61. H2 and P4 have no WiFi and
cannot be accessories. v0 targets the dev boards on the bench (§15 Q11).
Battery accessories must listen continuously for the beacon, which rules out
deep sleep between beacons (§15 Q12).

**None connect to the main board**, except the PWM pump header, which is a
plain board pin and not an Isotope device (no MCU on the far end).

**The hub side (Flagship):** the P4 has no radio. The C6 on its tag-on board
is an esp_hosted slave over SDIO, and stock esp_hosted has no ESP-NOW in its
RPC surface. Two pieces close that:

- **Co-processor image:** ESPHome's
  [esp-hosted-firmware](https://github.com/esphome/esp-hosted-firmware),
  which "bridges the native esp_now_* API over ESP-Hosted's CustomRpc
  channel" for ESP32, C5, C6 and C61 over SDIO. The overlay "only applies to
  ESP-Hosted >= 2.8.1". Its PR
  ([#17](https://github.com/esphome/esp-hosted-firmware/pull/17), merged
  2026-09-01) reports "Wi-Fi STA + ESP-NOW simultaneously" on real P4 + C6
  hardware, pushes received frames to the host as CustomRpc events, and
  defers esp_hosted 3.x. Nucleus today runs Espressif's stock slave image,
  so this is a Nucleus change.
- **Host shim:** [esphome PR 17712](https://github.com/esphome/esphome/pull/17712)
  (merged 2026-09-06) implements `esp_now_*` on the P4 by forwarding over
  CustomRpc, with a local peer-table mirror. Nucleus is pure ESP-IDF, not
  ESPHome, so the shim is ported or vendored, not linked.

  **Risks: three bugs the shim's review left open at merge**, each quoted
  from the PR, each a hub-side acceptance item (iso-3ph.4):
  1. *Send can stall forever.* "A lost SEND completion permanently stalls
     the ESP-NOW transmit path": no timeout, the send queue fills. This
     stops the beacon, so every accessory fails safe (the right direction),
     but the hub goes deaf-mute to its whole spoke network until it notices.
     The port needs a completion timeout.
  2. *Peer table stale after a C6 restart.* The C6 clears its peer table
     while the host mirror keeps its entries, so `esp_now_is_peer_exist()`
     keeps returning true, "peers are never re-added and the device goes
     quiet." The port must re-add every peer when the co-processor restarts.
  3. *A full table reports success.* Past 20 peers, `esp_now_add_peer()` has
     "already returned ESP_OK" while the mirror drops the entry, and the
     component re-issues ADD_PEER on every frame from that peer: "a permanent
     RPC flood". The hub's join path must check the peer count itself and
     refuse the join (§7 step 4), never trust the return code.
  [tymorton/esp32-p4-c6-espnow-enabler](https://github.com/tymorton/esp32-p4-c6-espnow-enabler)
  shows the C6 reflash over SDIO and runs SDIO at 10 MHz "for maximum
  stability".

**BLE** rides the same esp_hosted pair and is needed by config mode; Nucleus
has no BLE yet.

**Far future:** a dual- or tri-band hub board keeps the spoke network on its
own 2.4 GHz co-processor, off the station's channel, which deletes §6's
channel-follow problem. The part the operator named ("ESP32-E22") is
unverified.

## 14. The RFCs behind this design (Valence repo)

Accepted by the operator 2026-10-01 (RFC-085 2026-10-02) and landed; SPEC
sections at Valence 9dd395d.

| RFC | Landed | What it settled here | SPEC |
|---|---|---|---|
| RFC-075 ESP-NOW spoke binding | 8484552 | the spoke, beacon payload and cadence, active scan, the deadman, unencrypted operation (H13), the peer limit | §13.3.1 |
| RFC-076 Accessory join and declaration | b18fac1 | JOIN frames, 32-id slices, the declaration as a catalog, `safe`, persistence, sticky slices | §8.10, §13.3.2 |
| RFC-077 Live catalog growth | 4c0ede7 | user-space growth without revoking readiness, `CHANNEL_WITHDRAWN`, hub-advertised capacity | §8.6, §8.10 |
| RFC-078 Accessory conformance profile and the hub relationship engine | ede1f46 | the `accessory` and `accessory-host` profiles, accessory-status, the seven maps, the relationships STORE, the interlock | §17.1.1, §8.11, §11.6 |
| RFC-079 Config mode and the setup category | 4d267b0 | config mode over BLE and USB serial: no WiFi, no softAP, no spoke | §13.4.1 |
| RFC-085 Three safety pairs | 1ddf8af | PAUSE as the stop that reaches accessories through the interlock | §11.1, §11.6 |

## Out of scope

Encryption; mesh routing or any relay; accessories talking to each other or
to a client; accessories on the main board (the PWM pump header is a board
pin, not an Isotope device); an accessory commanding machine motion.

## 15. Open questions

0. **CANON FLAG -- the hardware SPEC says PAIR held at power-on opens AP
   config mode.** ANSWERED 2026-10-01 for Isotope (RFC-079; SPEC §13.4.1):
   config mode is BLE and USB serial, no WiFi, no softAP, no spoke. Still
   owed in the Hardware repo, its home: `../Hardware/flagship/SPEC.md:66`
   (2026-09-23 row) still reads "held at power-on = AP config mode".
1. **Scan form.** ANSWERED 2026-10-01 (RFC-075; SPEC §13.3.1 item 4): active,
   one DISCOVER_PROBE per channel, channels 1 to 13. iso-3ph.2 still
   measures the join time. (§6)
2. **ESTOP fan-out.** ANSWERED 2026-10-01 (RFC-075, RFC-085; SPEC §13.3.1
   items 3, 5 and 7, §11.6): yes, a latched e-stop puts every accessory in
   its safe state (spoke ESTOP repeats plus `estop_latched`); no STOP or
   PAUSE bit, pause rides the interlock. (§4, §9)
3. **Accessory channel budget and id range.** ANSWERED 2026-10-01 (RFC-076,
   RFC-077; SPEC §8.10): the budget is declared and hub-advertised, the
   library catalog capacity is a hub build parameter, and ids are 32-id
   slices of the user space, 30 own channels per accessory. (§8, §16)
4. **Default labels.** ANSWERED 2026-10-01 (RFC-076; SPEC §8.10, Appendix
   C): every entry carries its REQUIRED `name` (up to 32 B), so the config
   `key` is the default label; the hub-authored name is the accessory's
   (`accessory-admin` `rename`). (§8)
5. **What resets the deadman.** ANSWERED 2026-10-01 (RFC-075; SPEC §13.3.1
   item 5): only a matching BEACON; one clock. (§5)
6. **A reflashed accessory.** ANSWERED 2026-10-01 (RFC-076; SPEC §13.3.2):
   re-admitted without a window, declaration refetched and replaced in the
   same slice, relationships whose target field is gone disabled. (§7)
7. **One grant per window, or many?** ANSWERED 2026-10-01 (RFC-076; SPEC
   §13.3.2): one join per window; a `configure` session may open it
   in-band; pairing waits until the hub has joined WiFi (RFC-079). (§7)
8. **Relationship authoring surface.** ANSWERED 2026-10-01 (RFC-078; SPEC
   §8.11): the core relationships STORE and the RFC-067 store verbs; no
   sixth RFC, no relationship-admin channel. (§9)
9. **Generator shape:** compiled per config, or prebuilt image plus config
   partition? (§11)
10. **Where the web flasher and builder live:** this repo or Phosphor. (§11)
11. **v0 chip list:** which dev boards are on the bench. (§13)
12. **Battery accessories:** accept continuous receive, or design a
    duty-cycled beacon window? (§13)
13. **Deadman range.** ANSWERED 2026-10-01 (RFC-075, RFC-076; SPEC §13.3.1
    item 5, §13.3.2): declared per accessory in JOIN_REQ `deadman_ms`, 5 s
    by default, shorter allowed, never below 2 s. (§5)
14. **License:** operator decision, not chosen.
15. **CANON FLAG -- `safe: hold` has no wire form.** (§5, §10.2)
    Source A: this document's `hold` safe state for position actuators
    (stop driving, stay put). Source B: SPEC §8.8 makes `safe` a typed value
    inside the field's `min`/`max`, and §13.3.1 item 5 holds every actuating
    field at it, so a position target's safe value is a position and
    entering safe would drive toward it.
    My read: B binds; a position-following stand needs either an RFC (a
    hold meaning for a `command.position` field's safe state) or a remodel
    (a `drive` enable with safe `false` beside the target, the firmware
    never moving while disabled). The RFC is the honest one: the remodel
    reports a target value the actuator is not seeking.
    Your call: RFC, or remodel the stand? (`iso-42u`)
16. **A hub that reboots inside the deadman window.** SPEC §13.3.2 says a
    host reboot "needs nothing extra: every accessory's deadman fires". That
    holds for a planned reboot (GOODBYE) and for one longer than the window.
    A crash-reboot shorter than it need not fire it: the restarted beacon
    `seq` is newer or older under §7.3 depending only on where the old one
    stood, so the accessory may keep accepting beacons, keep its last
    commanded value and never rejoin, while the rebooted host has every
    relationship disarmed (§11.6).
    Proposal: Isotope treats a `boot_id` change from its hub as a deadman
    fire (`safe_deadman`, rescan, rejoin), and the case goes to the Valence
    queue as an RFC so every accessory does the same. (`iso-djk`)

## 16. Frame budget (paper, iso-3ph.8)

`tools/frame_budget.py` byte-counts the spoke frames as SPEC §13.3.1 and
§13.3.2 pin them, and a worst-case declaration as §8.10 defines it: a §8.1
catalog (CDDL, Appendix C) in the §5.3 deterministic profile, every layout
field carrying `size` (key 18) as the reference encoder emits it (§5.4),
every INTENT field carrying `safe` (key 25). A worst-case channel is one
field with every string at its CDDL maximum (entry name 32 B, field name
24 B, unit 8 B), f32 min, max and scale or `safe`, `category` set, no
`desc`, at a relative id of `0x18` or more (two CBOR bytes). Its output at
Valence 9dd395d, verbatim:

```text
BEACON: 8 + 22 = 30 B of 250
JOIN_REQ: 8 + 52 = 60 B of 250
JOIN_REPLY: 8 + 18 = 26 B of 250
BLOB_CHUNK: 8 + 14 + 192 = 214 B
entries: status (r=0x01) 102 B; at r>=0x18 readout 117 B, actuator 117 B, mirrored pair 234 B
30 actuators: 3592 B, 19 chunks at 192, 15 frames at 242; in the hub catalog 3646 B
30 readouts: 3592 B, 19 chunks at 192, 15 frames at 242; in the hub catalog 3646 B
15 mirrored pairs: 3592 B, 19 chunks at 192, 15 frames at 242; in the hub catalog 3646 B
one 242 B payload holds the status entry and 1 worst-case channel; one 192 B chunk holds 1 entry
status + 1 worst-case actuator: 219 B, 2 chunks at 192
hub PSRAM per accessory (Nucleus budget): pools 7612 B + encode scratch 6400 B = 14012 B
hub flash per accessory: declaration A/B 8192 B at the ceiling, 7184 B at the worst case
```

- **The declaration is 3,592 B in 19 chunks of 192 B**, 116.3 B per channel
  beside the 102 B status entry, under `accessory_declaration_max_bytes`
  (4,096 B) with 504 B spare. With `size` counted, a readout and an actuator
  cost the same 117 B, so the mix of the 30 does not move the total. Text
  (name, field name, unit) is 69 of the 117 B; short keys and units shrink it
  most.
- **It rides blob chunking, never one frame.** One 242 B payload holds the
  status entry and one worst-case channel, so a declaration is the
  accessory's blob namespace 0 (SPEC §8.10, §13.3.2), which §13.3.1 item 1's
  ban on §5.6 fragmentation already requires. 19 chunks inside
  `frag_reassembly_timeout_ms` (5 s) is 4 chunks a second. The 15 frames at
  242 B are for comparison only: a declaration may not ride raw payloads.
- **In the hub catalog it is 3,646 B**: the host re-encodes relative ids as
  absolute ones (`0x8000` and up, three CBOR bytes each), inside the 5,120 B
  per-accessory encoded-catalog budget Nucleus sized for.
- **Hub cost per accessory: about 14.0 KB of PSRAM and 8 KiB of flash**,
  reconciled with Nucleus `docs/accessory-store-sizing.md` (its home): pools
  of 31 entries, 33 layout, 30 schema and 64 labels at the 32-bit slot sizes
  are 7,612 B, the encode-scratch share is 5,120 B / 0.8 = 6,400 B, and the
  declaration kept A/B at its ceiling is 8,192 B of flash (7,184 B at this
  worst case). Nucleus's totals for 6 accessories (~87 KB PSRAM, 48 KiB
  flash) agree once its scratch round-up to 72 KiB is counted. Every
  worst-case shape fits those pools: 30 actuators use 31 entries, 3 layout
  and 30 schema fields; 30 readouts 31, 33 and 0; 15 mirrored pairs 31, 18
  and 15.
- **Spoke control frames all fit:** BEACON 30 B, JOIN_REQ 60 B, JOIN_REPLY
  26 B, BLOB_CHUNK 214 B, each under 250. Paper only: the beacon on the wire
  is iso-3ph.1's first measurement.

## 17. Conformance checklist: the `accessory` profile

What every generated Isotope image owes, from SPEC §17.1.1 (RFC-078) at
Valence 9dd395d, each duty with the firmware module that will own it. No
firmware exists; the module names are the proposed split, fixed when the
generator shape is (§15 Q9). Every wire number comes from the Valence
generated registry (`lib/valence/include/valence/generated/registry_constants.hpp`),
never a local constant.

| # | Duty | SPEC | Owner |
|---|---|---|---|
| 1 | **Parser totality**: every malformed or oversize frame refused, never a crash or a partial apply | §5.8, §17.1 | `wire` (the Valence library decoders), `link` (length gate before decode) |
| 2 | **Exact encoding**: §5.1 header, §5.3 CBOR profile, §5.4 packed layouts, golden-vector exact | §17.1.1, §17.2 | `wire` |
| 3 | **Declaration**: a §8.1 catalog with relative ids `0x01`-`0x1F`, at most 30 own channels, `safe` on every value-bearing INTENT and c2h STREAM field, the §8.10 validation rules, no STORE entries, within 4,096 B | §8.10, §8.8 | generator (builds and lints it), `declaration` (holds the bytes and etag) |
| 4 | **Serve the declaration** as blob namespace 0 over BLOB_REQ/BLOB_CHUNK with §8.4 pacing, its etag in JOIN_REQ | §8.4, §13.3.2 | `declaration` |
| 5 | **ECHO or NACK on every INTENT**, post-clamp and key-complete, idempotent over at least the latest `intent_id` | §9.3, §17.1.1 | `intent` |
| 6 | **Clamping**: every received actuating value clamped into its declared `min`/`max` before it reaches a pin | §13.3.1 item 2 | `channels` |
| 7 | **c2h STREAM intake**: §5.4 caps checked, violators dropped whole, samples applied on arrival keeping `t_off`; no CLOCK | §17.1.1 | `stream` (only in images that declare one) |
| 8 | **STATE push** at each channel's `max_rate_hz` (on change for 0), no SUBSCRIBE: the host is the implicit subscriber | §17.1.1 | `channels` |
| 9 | **Accessory-status at `r = 0x01`**: `{state u8, fault u8, beacon_seq u16}`, on change and at least every `spoke_beacon_interval_ms` | §17.1.1, registry `accessory_status` | `safety` |
| 10 | **Channel follow**: active scan on channels 1 to 13, one DISCOVER_PROBE per channel, `spoke_scan_dwell_ms` dwell, "my hub" by source address and `hub_instance_id`, retune to `wifi_channel` | §13.3.1 items 3, 4 | `scan` |
| 11 | **Deadman and safe state**: the four doors, only BEACON refreshes, `safe` values held, verbs abandoned, the sticky exits, never self-restoring | §13.3.1 item 5 | `safety` |
| 12 | **ESTOP**: a valid CRC-checked ESTOP from any source enters `safe_estop`; never rebroadcast | §13.3.1 items 5, 7 | `safety` |
| 13 | **250 B budget**: every spoke frame fits one ESP-NOW v1 payload with its header; no §5.6 fragmentation | §13.3.1 item 1 | `link` |
| 14 | **Reliability**: ACKMASK every 10 ms, stop-and-wait 3 x 100 ms for control frames, no retransmit of STATE or STREAM | §13.3, §13.3.1 item 6 | `link` |
| 15 | **Durable `accessory_id`**: random u64 at first boot, persisted across reboots and firmware updates; the paired hub's `hub_instance_id` and address persisted | §8.10 | `identity` |
| 16 | **Join**: pairing state by gesture or factory-fresh, JOIN_REQ once per matching BEACON until answered, rejoin on every reacquisition, every `join_results` value handled, safe after any join | §13.3.2 | `join` |

**Absent by profile, never built:** HELLO/WELCOME and the rest of the
session layer, the readiness gate, SUBSCRIBE/UNSUBSCRIBE/GRANT/PUBLISH,
PROBE, CLOCK, access tiers, pairing tokens, AUTH, HUB_SIG, the trust ledger,
every core channel, control ownership, multiple peers, BLE GATT, WebSocket,
discovery, and the rendering annotations beyond what §8.10 requires
(§17.1.1).

**Modules, one line each.** `wire`: the Valence library's codec and
generated constants, linked, not copied. `link`: the ESP-NOW peer, send gate
and reliability layer. `scan`: probe, beacon match, retune. `join`: pairing
state and the JOIN exchange. `identity`: the persisted ids. `declaration`:
the baked catalog bytes and the blob server. `intent`: INTENT in, ECHO or
NACK out. `channels`: the actuator and readout drivers, clamping and STATE
pushes. `stream`: bundle intake. `safety`: the deadman clock, the safe-state
machine and accessory-status.
