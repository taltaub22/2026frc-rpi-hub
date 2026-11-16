# Cheesy Arena integration notes

Verified against Team254/cheesy-arena `main`, commit 248d9de (19 Oct 2026), `plc/plc.go`.
Re-check the const blocks if you move to a newer main.

Cheesy Arena polls ONE PLC address (port fixed at 502) every 100 ms:
FC2 read 28 discrete inputs @0, FC3 read 11 holding registers @0, FC15 write 13 coils @0.

## Discrete inputs (28)
| Idx | Meaning | We return |
|-----|---------|-----------|
| 0-12 | fieldEStop, EStop+AStop for Red1-3, Blue1-3 (INVERTED: false = pressed) | 1 |
| 13-18 | red/blue Connected 1-3 (display only) | 1 |
| 19 | ftaReady (required true to start a match) | 1 |
| 20-23 | redHubSensor1-4 live level | live |
| 24-27 | blueHubSensor1-4 live level | live |

## Holding registers (11)
| Idx | Meaning | We return |
|-----|---------|-----------|
| 0 | fieldIoConnection bitmask (redDs, blueDs, redIoLink, blueIoLink = bits 0-3) | 0x000F |
| 1 / 2 | redHubTotal / blueHubTotal (16-bit) | cumulative |
| 3-6 / 7-10 | per-sensor counts red / blue | cumulative |

## Coils (13, written as one block)
0 heartbeat (ignored) | 1 matchReset (zero on rising edge; held ~6 cycles) | 2-8 lights (ignored) |
9, 10 hub motors (later: relay) | 11, 12 hub lights (ignored)

## Match start conditions (when PLC address is set)
PLC healthy, field E-stop not active, ftaReady true, fieldIoConnection bits 0-3 set.

## Gate 0
1. Cheesy Arena build has `GetHubCounts()` and the 28/11/13 sizes.
2. Settings page has a PLC address field: set to the server Pi (10.0.100.40).
3. With the Pi attached, no "PLC is not healthy" / "FTA ready" / "ArmorBlock" messages when starting a match.

## Two hubs, one address
Server Pi 10.0.100.40 serves Modbus for both hubs; peer Pi 10.0.100.41 sends UDP (port 5021)
state ~10x/s. On matchReset the server zeroes, bumps a reset epoch, and sends it to the peer;
state updates with an old epoch are ignored.
