# Hub box wiring (per hub, x2)

Per hub: 4x E18-B03P1 (PNP, 6-36 V), 1x PC817 4-ch opto module, 12 V 5 A adapter,
WAGO 221 (+12 V), Phoenix PTFIX 12x2.5 (GND), enclosure, Raspberry Pi + PoE HAT.

## Channel map (single source of truth for wiring and code)
| Ch | Sensor | Brown (+12V block) | Blue (GND block) | Black -> module | Module out | Pi GPIO (BCM) | Pi pin |
|----|--------|--------------------|------------------|-----------------|------------|---------------|--------|
| 1  | S1 | pin 2 | pin 2 | IN+ 1 | OUT 1 | 17 | 11 |
| 2  | S2 | pin 3 | pin 3 | IN+ 2 | OUT 2 | 27 | 13 |
| 3  | S3 | pin 4 | pin 4 | IN+ 3 | OUT 3 | 22 | 15 |
| 4  | S4 | pin 5 | pin 5 | IN+ 4 | OUT 4 | 23 | 16 |

`CFG["pins_bcm"]` in `src/fuelhub.py` must match this table.

## +12 V block (WAGO 221, 5 contacts)
1 = adapter +12 V (direct, no fuse); 2-5 = brown wires of S1-S4.

## GND block (PTFIX 12-pole)
1 = adapter minus; 2-5 = blue wires S1-S4; 6-9 = module IN- 1..4; 10-12 free.

## Pi side
| Module pin | Pi pin |
|------------|--------|
| VCC (output side) | 1 (3V3) |
| GND (output side) | 6 (GND) |
| OUT 1-4 | 11, 13, 15, 16 |

The 12 V ground and the Pi ground are NOT connected. The opto module is the isolation barrier.

## Build notes
- Ferrules on all stranded wire (push-in blocks). Strain relief at every gland.
- Label cables S1-S4 at both ends, plus wire colors.
- Decision: no fuse. Keep 12 V wiring short, insulated, and away from the Pi side.
- Module pin labels/polarity are undocumented: check silkscreen, measure with a multimeter before connecting the Pi.
- Check the PoE HAT leaves pins 1, 6, 11, 13, 15, 16 reachable.
- Bench-test every channel with a real ball before closing the box.
- Polarity: if the module output idles low, set `active_high` accordingly in `CFG`.
