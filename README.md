# Isotope

> **Nothing here runs yet.** This repo is a design home: `docs/DESIGN.md`
> plus the validation plans on the dev board (`bd`, prefix `iso`). No
> firmware, generator, flasher or builder exists. Every protocol claim in the
> design cites the Valence spec or names the RFC that must land first.

**Valence Isotope** is the firmware for Valence accessories: the small
ESP32-family devices (a peristaltic pump, a motorized stand)
that join a Valence hub over ESP-NOW and appear in its catalog as ordinary
channels. Same thing as the hub, small variation. An accessory is described
by a declarative config, ESPHome-shaped; a generator turns that config into
an image; the accessory declares its own channels to the hub when it joins,
and the hub, never the client, runs the relationships that drive it. Every
accessory fails safe on its own: no hub beacon for five seconds, or a
goodbye, and each actuator goes to its declared safe value.

## The order things get built

1. **Config format + generator.** The declarative config is the one home for
   what an accessory is. The generator turns it into a flashable image.
2. **Web flasher.** A browser page that takes a config, produces the image
   and flashes it over Web Serial.
3. **Visual builder.** A blueprint-style editor on top of the config. It
   emits the same config; it never has a capability the config lacks.

Each step waits on the validation epic on the board: nothing is built until
the radio numbers it depends on are measured on dev boards.

## Its relatives

| repo | what it is | how Isotope touches it |
|---|---|---|
| [`../Valence`](../Valence) | the protocol: SPEC, registry, conformance | **read-only.** Every wire number and behavior comes from there. What Isotope needs and the spec lacks becomes an RFC there first. |
| [`../Nucleus`](../Nucleus) | the reference hub (OSSM Flagship firmware, P4 + C6) | the other end of every accessory link: beacon, join, declaration store, relationships. Hub-side work is filed on Nucleus's own board. |
| [`../Phosphor`](../Phosphor) | the reference client | renders accessory channels like any catalog channel; authors hub-side names and relationships. Never talks to an accessory directly. |
| [`../Hardware`](../Hardware) | board designs | the Flagship's C6 radio and the PWM pump header. |

All sit beside this repo in the same parent directory.

## License

Not chosen. The license is an operator decision; until it is made, nothing
here is licensed for reuse.

## Where the rules live

- `.claude/rules/governance.md`: a pointer to the Valence canon, not a copy.
- `docs/DESIGN.md`: the design rulings and the open questions.
- The dev board (`bd`, prefix `iso`): volatile truth, validation plans,
  results.
