# Over-the-air code updates

From your laptop, on the field network, with the repo checked out:
```
./provision/ota.sh                  # peer (blue) first, then server (red)
./provision/ota.sh --only peer      # one Pi
./provision/ota.sh --force          # even if a match may be running
```
`ota.sh` packages `src/fuelhub.py` with a version (`git describe`), uploads it with a SHA-256, and runs
`fuelhub-apply` on each Pi over SSH.

## What makes it safe
| Step | Protection |
|------|------------|
| Upload | sha256 checked on the Pi; a corrupt or truncated upload is rejected (exit 2) |
| Unpack | new code is `py_compile`d before it is used; a syntax error never goes live (exit 2) |
| Switch | each release lives in `/opt/fuelhub/releases/<version>`; `current` is an atomic symlink swap |
| Restart | `fuelhub --selfcheck`: status file fresh, and (server) a real Modbus read with the required bits set |
| Failure | automatic rollback to the previous release, restart, selfcheck again (exit 1) |
| Match running | refuses to restart if pulses were counted in the last 60 s, because a restart zeroes that hub's counts (exit 3) |
| Both Pis | peer first; if it fails the server is not touched. The UDP link carries a protocol number, mismatches are logged |
| History | last 3 releases kept; `ls /opt/fuelhub/releases`, logs in `journalctl -t fuelhub-apply` |

## Manual rollback
```
ssh pi@10.0.100.40 'sudo ln -sfn releases/<old-version> /opt/fuelhub/current && sudo systemctl restart fuelhub'
```

## Check what is running
`python3 /opt/fuelhub/current/fuelhub.py --version` or `--selfcheck` on the Pi; `/run/fuelhub/status.json` has
version, counts and seconds since the last pulse.

## Limits
- Needs SSH reachability (laptop on 10.0.100.0/24). No internet needed.
- Updates the application only. OS, network settings and role changes mean re-flashing (zero-touch, 2 minutes).
- Updating the same version twice is a no-op; a dirty git tree gets a unique version each time.
