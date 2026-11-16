# fuelhub

Raspberry Pi REBUILT Fuel hub counter for FIRST Israel off-season events.
Each Pi counts sensor pulses (4 photoelectric sensors per hub) and answers
[Cheesy Arena](https://github.com/Team254/cheesy-arena) over Modbus TCP, behaving like the
Allen-Bradley PLC it already talks to. **Cheesy Arena stays unmodified** (except `network/switch.go`
for UniFi, tracked separately).

Targets Cheesy Arena `main` at 4ceffb5. Status: first draft. Passes local tests against the `plc/plc.go` map; NOT yet tested on a Pi,
with real sensors, or against a running Cheesy Arena.

## Layout
- `src/fuelhub.py` - the counter + Modbus PLC emulator (stdlib only, `gpiozero` for GPIO)
- `tests/` - unit + Modbus protocol tests (`python3 -m unittest discover -s tests`; also `bash tests/test_apply.sh`)
- `tools/modbus_probe.py` - mimics Cheesy Arena's poll; add `--reset` to test matchReset
- `deploy/` - `fuelhub-apply.sh` (safe release installer on the Pi), systemd unit template, SSH install fallback
- `provision/` - `make_sd_config.py` (zero-touch cloud-init), `flash.sh`, `ota.sh`, `verify.sh`, `deploy.sh`, role settings
- `docs/flashing.md` - **start here: zero-touch flashing**; `docs/ota.md` - code updates over the network
- `docs/wiring.md` - hub box wiring and channel map
- `docs/cheesy-arena-integration.md` - register map and match-start requirements

## Two hubs, one PLC address
| Pi | IP | Command |
|----|----|---------|
| Server (red hub) | 10.0.100.40 | `fuelhub.py --serve --alliance red --peer 10.0.100.41` |
| Peer (blue hub)  | 10.0.100.41 | `fuelhub.py --alliance blue --peer 10.0.100.40` |

Set Cheesy Arena's PLC address to `10.0.100.40`.

## Quick start (no hardware)
```
python3 src/fuelhub.py --serve --alliance red --simulate --port 5020
python3 tools/modbus_probe.py 127.0.0.1 --port 5020
```

## Set up a Pi (no keyboard, mouse, or screen)
`sudo ./provision/flash.sh server /dev/sdX` (or `peer`), put the card in the Pi, power it, wait 2 minutes,
`./provision/verify.sh server`. Details and the GUI-Imager route: `docs/flashing.md`.

## Update code later
`./provision/ota.sh` : verified, versioned, health-checked, auto-rollback, refuses mid-match. See `docs/ota.md`.

## To do
- Bench-measure PC817 module polarity (`active_high`) and tune `refractory_s` (start 30 ms)
- Per-pulse CSV logging for audits
- "Peer last seen" warning; hub-motor relay from coils 9/10
- Optional real field E-stop and FTA-ready buttons on spare GPIOs (DI 0 and 19)
- Accuracy target: <= ~0.074% double counts (FIRST Week 0 measurement)

## Validation plan
Bench per channel -> 100-500 balls per hub vs manual count -> edge cases (touching balls, slow balls,
lighting) -> Modbus client test -> Cheesy Arena test matches -> full dress rehearsal.

## License
MIT, see `LICENSE`.
