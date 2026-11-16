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
- `tests/` - unit + Modbus protocol tests (`python3 -m unittest discover -s tests`)
- `tools/modbus_probe.py` - mimics Cheesy Arena's poll; add `--reset` to test matchReset
- `deploy/` - `install.sh` (runs on the Pi) and the systemd unit template
- `provision/` - `deploy.sh` (laptop -> Pi), `verify.sh`, `lock-root.sh`, per-role settings in `roles/`
- `docs/flashing.md` - **start here to set up a Pi**
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

## Set up a Pi
Flash Raspberry Pi OS Lite 64-bit, then `./provision/deploy.sh server user@fuelhub-red.local`
(or `peer`), reboot, `./provision/verify.sh server user`, then lock the root filesystem.
Full steps: `docs/flashing.md`. Port 502 is bound via `CAP_NET_BIND_SERVICE`.

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
