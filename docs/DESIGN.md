# Isotope: design

> **Nothing here is built.** Home of Isotope's design rulings (C-1: this is
> that fact's one home). The rulings are the operator's of 2026-09-26; where
> this document goes beyond them it says "proposal" and the question is in
> §15. Wire truth stays in the Valence repo; every protocol claim below cites
> a SPEC section or names the RFC that must land first. Those RFCs are named
> by title (§14), not number: they are being drafted and have none yet.
> Status and measured numbers live on the dev board (`bd`, prefix `iso`).

## 1. What Isotope is

The accessory firmware of the Valence ecosystem. An Isotope device is a
small ESP32-family board driving one accessory (a pump, a vibrator, a
motorized stand) that joins ONE Valence hub (Nucleus) over ESP-NOW,
declares its channels, obeys the hub, and fails safe on its own.

Three artifacts, built in this order and no other:

1. **Config format + generator.** A declarative, ESPHome-shaped config is
   the one home for what an accessory is. The generator turns it into an
   image.
2. **Web flasher.** Config in, flashed board out, from a browser.
3. **Visual builder.** A blueprint-style editor over the config. It emits
   the same config and never has a capability the config lacks.

## 2. Where Valence stands today, and what it must learn

What the spec already has:

| Fact | Where |
|---|---|
| ESP-NOW is a binding: 250 B frame, 242 B payload after the 8-byte header, unordered, unreliable, ACKMASK loss signal, control frames stop-and-wait 3x at 100 ms, no retransmit of STATE/STREAM | SPEC §13.1 matrix, §13.3 |
| The ESP-NOW line IS the normative floor: every STATE payload fits 242 B | §13.1, §9.1 |
| A BEACON frame (`0x17`, raw, channel 0: `boot_id`, catalog etag, pairing-open flag) broadcast every 500 ms, ONLY while a pairing window is open | §13.7 |
| ESP-NOW is "deliberately trivial to enable, not itself conformance-relevant" | §13.1 (RFC-043) |
| A valid ESTOP frame from ANY ESP-NOW peer, paired or not, MUST be honored; the beacon reserves a `datagram_estop` flag bit | RFC-053 items 2 and 2b (accepted) |
| Push-to-pair: a physical-presence proof opens a short window | §12.3(c), RFC-027 |
| The catalog is fixed per firmware; a change changes the etag and is signaled on the `catalog` STATE channel | §8.6, §8.3 |
| The deadman forces no stop on the hub side; it is liveness bookkeeping | §11.3 (RFC-045) |
| A hub MAY span several physical devices; an internal link has no conformance duty | RFC-056 item 1 (PROPOSED) |

Where the rulings move past the spec (each is an RFC, §14):

- **The beacon becomes a permanent 1 Hz heartbeat**, not a 500 ms
  pairing-only broadcast (§13.7). It also gains the hub's durable id and its
  WiFi channel.
- **No encryption.** §12.9 says ESP-NOW pairing "MAY carry segment keys"
  and that "unencrypted operation remains permitted for `watch`-class
  traffic", which implies control traffic should be keyed. The ruling runs
  every accessory link in the clear, so §12.9 needs an amendment and an
  honesty clause (§8 below states the consequence).
- **The catalog grows at runtime.** §8.6's "never created or destroyed at
  runtime" is exactly what pairing an accessory does.
- **A new role.** An accessory is not a client, not a hub and not a §14
  relay; §17.1 has no row for it. RFC-056 would let a hub treat its
  accessories as internal components with no spec duty, but that only works
  for first-party parts; community accessories must work with any hub, so
  the link needs a spec.
- **An accessory deadman DOES force a safe state**, unlike §11.3's hub-side
  deadman. Not a contradiction: §11.3 leans on §9.6 (every motion mode is a
  bounded plan that settles by itself). A pump that was told "on" has no
  plan to run out of; it stays on. That is the case §11.3 already carves out
  for hub-autonomous sources (`source.background_run`, default `false` =
  stop). The declared safe value is the accessory's equivalent of that
  default, fixed at flash time.

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
- **Never with the P4 in softAP mode** (ruling). No softAP ever, in any mode,
  including config mode.

## 4. The hub beacon

One broadcast every second, always, on the hub's current channel. It is the
accessory's only proof that the hub is alive, and its discovery signal.

Proposed payload (a Valence frame, `0x17` reshaped by the ESP-NOW binding
and beacon RFC):

| Field | Bytes | Why |
|---|---|---|
| header (§5.1): `type`, `flags`, `channel` 0, `seq`, `len` | 8 | `seq` is the beacon sequence number, free from the header |
| `hub_instance_id` u64 | 8 | durable cross-boot hub id (the §13.8 argument: a boot-scoped id cannot tell two hubs apart across a reboot). An accessory obeys only the hub it paired with. |
| `boot_id` u32 | 4 | a change means the hub rebooted and lost its retained values: the accessory goes safe and re-announces (§5) |
| `catalog_etag` | 8 | kept from today's BEACON for Valence-over-ESP-NOW clients |
| `wifi_channel` u8 | 1 | 2.4 GHz channels overlap; a beacon sent on 6 is often heard while tuned to 5 or 7. This field names the true one. |
| `flags` u8 | 1 | bit0 `pairing_window_open` (existing meaning, §13.7); bit1 `datagram_estop` (RFC-053 2b); bit2 `estop_latched` (proposal: every accessory holds safe while set); bit3 `going_away` (hub goodbye, §5); bits 4-7 zero |

Total 30 B of 250 (§16). RFC-075 item 3 pins the same 22-byte payload in a
different field order and flag-bit assignment (bit2 `accessory_host`, bit3
`estop_latched`; the goodbye is GOODBYE, not a bit); the RFC wins once
accepted, and the size is identical either way.

## 5. The accessory deadman

- **Five missed beacons = dead hub = safe state.** 5 s at 1 Hz. Only a beacon
  from the paired `hub_instance_id` resets the clock (proposal, matching the
  ruling's wording; whether hub unicast frames also count is §15 Q5).
- **Goodbye = safe immediately.** Two doors: a unicast GOODBYE (`0x11`,
  §6.9) to one accessory (unpaired, evicted), or a beacon with `going_away`
  set, repeated a few times, before a planned hub shutdown or reboot.
- **Also safe:** at power-on before the radio is up; when `boot_id` changes;
  while `estop_latched` is set (proposal).
- **Every actuating channel declares its safe value** at flash time: a value
  (`0`, `false`) or `hold` (stop driving and stay where it is, for position
  actuators, where "go to a safe angle" would itself be motion). Readouts
  declare none. The generator refuses an actuator without one.
- **Safe is sticky.** When beacons return, the accessory does NOT resume the
  last commanded value; it waits for a fresh one from the hub. This mirrors
  §6.8: "Motion never restarts because a socket reopened."
- **The false-trip arithmetic, stated so the bench can check it.** Broadcast
  frames get no MAC-layer retries, so beacon loss runs higher than unicast
  loss. With per-beacon loss `p`, five in a row happens roughly `p^5` of the
  time: at 10% loss about once a day of continuous use, at 30% about every
  seven minutes. Validation (a) measures `p`; (c) measures the trip itself.

Loss of the hub and loss of the channel look the same, and they share one
code path: safe, then rescan (§6).

## 6. Channel follow

At boot, and after any deadman trip, the accessory scans channels 1-13 for
its hub, adds the hub as a peer on the channel it found, and joins or
re-announces. A router that changes channel therefore costs one deadman trip
(5 s, safe) plus one scan. The BLE channel hint is NOT built (ruling).

**The scan is an active probe; the beacon stays for the deadman.** Passive
listening cannot meet the ruled ~2 s: a 1 Hz beacon lands inside a 150 ms
window only 15% of the time, so a passive listener needs about 1 s of dwell
per channel, about 13 s cold. So on each channel the accessory broadcasts a
tiny PROBE and the hub answers it at once, unicast, with the beacon's
payload (§4). That is the §13.8 DISCOVER_PROBE / DISCOVER_REPLY shape moved
onto ESP-NOW (and 802.11 active scanning's), and it makes the scan ~150 ms
per channel, 13 x 150 ms = ~2 s worst case. The 1 Hz beacon is untouched;
it is still the only thing that feeds the deadman (§5). Two rules follow:
the hub answers strangers' probes, so replies are rate-limited per source
the way §13.8 limits DISCOVER_REPLY; and channels 12-13 are receive-only in
some regulatory domains, so the accessory probes only on channels its
region allows and listens passively on the rest. Validation (b) measures
passive against active to confirm the arithmetic.

Config mode (no WiFi, §14) puts the hub's radio on a default channel; once
the hub joins a router, accessories lose it once and find it again through
this same path.

## 7. Join and pairing

Lineage: §12.3(c) push-to-pair (RFC-027): a physical-presence proof opens a
short window.

1. **The hub opens a window.** The operator holds the hub's pairing button at
   runtime. The beacon sets `pairing_window_open`. Window length defaults to
   `pairing_window_default_s` (120 s, §12.3) unless the RFC says otherwise.
2. **The accessory is in pairing state.** An unpaired Isotope device always
   is; a paired one enters it by holding its own button (config `pairing`).
3. **It finds the hub** (§6), sees the window flag, and sends a JOIN request:
   its durable id (from the eFuse MAC), its declaration etag, channel count,
   declaration size.
4. **The hub accepts** if the window is open, a peer slot is free and a
   channel slice is free. It assigns the slice, adds the peer, answers
   unicast, stores the pairing to flash.
5. **The accessory sends its declaration** (§8), chunked. The hub stores it,
   adds the channels to its catalog, and the etag changes (§8.3); every
   connected client re-syncs through the §8.6 path.
6. **Later boots need no window.** A known id with an unchanged declaration
   etag is re-admitted on sight. A changed etag (reflashed with a new config)
   is §15 Q6.

Bounded like §12.3(a): strangers' join requests outside a window are dropped
without an answer, and pending joins are capped (`pairing_pending_max`
lineage). Single-grant per window or many is §15 Q7.

## 8. Self-description and what the hub stores

**The accessory is self-describing.** Its channels, types, ranges and
deadman are baked in at flash time and declared to the hub on join as a
mini-catalog. Only hub-side things (names, relationships) are authored from
Phosphor.

Per channel, the declaration carries: relative id (`0x02`-`0x1F`, 30 at
most, SPEC §8.10), kind (actuator,
readout, event, estop button), `packed_field_types` value type, unit, scale,
min/max, safe value (actuators, REQUIRED), max rate. Per accessory: durable
id, model string, firmware version, deadman, declaration etag.

**One Isotope channel is one catalog entry.** The declaration IS the
accessory's catalog (SPEC §8.10), so a readout is a STATE entry and an
actuator an INTENT entry. Proposal: an actuator also gets a STATE readback
at the next relative id, because a client other than the writer learns an
applied value only from STATE (SPEC §9.3); that spends two ids per actuator,
so a slice holds 15 mirrored actuators. That also matches Phosphor's ruling
that a control is one channel field.

**The declaration does not fit one frame.** It rides application chunking
the way blobs do (§8.4, 192 B chunks), never §5.6 fragmentation, which is
for control frames only. Worst case it is 3,592 B in 19 chunks (§16).

**What the hub stores** (flash, unpacked to PSRAM at boot, ruling): the
declaration verbatim, the durable-id to MAC binding, the assigned slice,
hub-authored display names, and relationships. The accessory stores only its
hub's `hub_instance_id` and MAC.

**Commands are absolute and echoed.** The hub sends absolute target values
(§9.3's no-relative-intents rule: "set to 40", never "add 5"); the accessory
reports the value it applied; the hub resends until they match. Clients show
the accessory's reported value, never the hub's wish (ground-truth doctrine).

**Identity is not authenticated (honesty clause).** No encryption means any
radio in range can send frames with a paired accessory's MAC and id. The
exposure is bounded by one rule, proposed here as binding: **an accessory
never drives machine motion.** No relationship may target a motion channel;
the arbiter's sole-caller rule (§11.4) stands. A spoofer can fake readouts
and poke accessory actuators within their declared ranges; it cannot move
the machine. An accessory CAN always stop the machine (RFC-053: an ESTOP
frame from any peer), which is the safe direction.

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
accessory's own. The accessory speaks relative ids and never learns its
slice; a slice is sticky across reboots and declaration replacement and is
never reused after a forget (SPEC §8.10).

## 9. Relationships

A relationship is **hub policy**: a source field, a target accessory channel,
and a mapping. Source: any STATE field in the hub's catalog (machine
position, speed, another accessory's readout). Target: one accessory
actuator. Mapping (proposal): a clamped linear map, optionally a threshold,
at most the target's declared max rate.

- **Evaluated on the hub**, on source change, never on a clock (Nucleus
  motion doctrine: event-driven). Output clamped to the target's declared
  range.
- **Survives client loss.** Stored in hub flash; Phosphor closing changes
  nothing.
- **Targets accessories only** (§8's binding rule).
- **Deadman and estop win.** A relationship output never overrides the
  accessory's safe state.
- **Authored from Phosphor** through a hub-side surface (a STORE, §8.7, or a
  standard channel). None of tonight's RFCs covers it (§15 Q8).

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
  from the PR, each a hub-side acceptance item (validation (d)):
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

## 14. The RFCs this needs (Valence repo, by title)

| RFC (title) | What it settles here |
|---|---|
| ESP-NOW binding and hub beacon | §4 beacon shape and cadence; §6 probe form; §12.9 amendment for unencrypted operation plus its honesty clause |
| Live catalog growth | §8.6 amendment: channels added and removed at runtime, mid-session re-announce |
| Accessory conformance profile | the accessory role and its §17.1 row; the safe-state duty (§5) and why it differs from §11.3 |
| Accessory join and declaration | JOIN frames, slice allocation, the channel-id range and hub budget, the declaration encoding and its chunking |
| Config mode | boot-with-button provisioning over BLE (RFC-054 and RFC-069 lineage): no WiFi, window open, setup category |
| *(not drafted)* Relationship surface | how a client authors and reads relationships (§9) |

## Out of scope

Encryption; mesh routing or any relay; accessories talking to each other or
to a client; accessories on the main board (the PWM pump header is a board
pin, not an Isotope device); an accessory commanding machine motion.

## 15. Open questions

0. **CANON FLAG -- the hardware SPEC says PAIR held at power-on opens AP
   config mode; the 2026-09-26 rulings forbid softAP.**
   Source A: `../Hardware/flagship/SPEC.md:66` (2026-09-23 row): "SW2 PAIR
   (hold = pair, held at power-on = AP config mode, press TBD)".
   Source B: the 2026-09-26 rulings: config mode is "pairing window open, BLE
   advertising with the window flag, no WiFi", and "No softAP ever"
   (ESP-NOW never runs with the P4 in softAP mode).
   My read: B is newer and deliberate; A predates the ESP-NOW decision. The
   button and its "held at power-on" gesture are unchanged, only the mode it
   enters moves from AP to BLE. Firmware behavior is Nucleus's, but the
   hardware repo's row is the stated home and reads as current.
   Your call: amend the hardware SPEC row to "held at power-on = config mode
   (BLE, no WiFi)", in the hardware repo, dated?
1. **Scan form.** Designed as an active probe (§6). Confirm, once
   validation (b) has measured passive against active.
2. **ESTOP fan-out.** Does a latched machine e-stop put every accessory in
   its safe state (the `estop_latched` beacon bit)? (§4)
3. **Accessory channel budget and id range.** ANSWERED 2026-10-01 (RFC-076,
   RFC-077; SPEC §8.10): the budget is declared and hub-advertised, the
   library catalog capacity is a hub build parameter, and ids are 32-id
   slices of the user space, 30 own channels per accessory. (§8, §16)
4. **Default labels.** Does the declaration carry each channel's config
   `key` as a default display name, or is a fresh accessory shown as
   "channel N" until named in Phosphor? (§8)
5. **What resets the deadman:** only beacons, or any frame from the hub? (§5)
6. **A reflashed accessory** (same id, new declaration): re-admitted
   automatically, or held offline until a pairing window? Relationships
   pointing at removed channels need an answer either way. (§7)
7. **One grant per window, or many?** (§7)
8. **Relationship authoring surface:** a sixth RFC, or a device STORE plus a
   role? (§9)
9. **Generator shape:** compiled per config, or prebuilt image plus config
   partition? (§11)
10. **Where the web flasher and builder live:** this repo or Phosphor. (§11)
11. **v0 chip list:** which dev boards are on the bench. (§13)
12. **Battery accessories:** accept continuous receive, or design a
    duty-cycled beacon window? (§13)
13. **Deadman range:** fixed 5 s, or declared per accessory within a clamp?
    (§5)
14. **License:** operator decision, not chosen.

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
