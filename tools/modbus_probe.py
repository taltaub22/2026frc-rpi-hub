#!/usr/bin/env python3
"""Mimics Cheesy Arena's 100 ms PLC poll against a fuelhub server (FC2 28, FC3 11, FC15 13).
Usage: python3 tools/modbus_probe.py HOST [--port 502] [--reset] [--once]
"""
import argparse, socket, struct, time

def txn(s, tid, pdu):
    s.sendall(struct.pack(">HHHB", tid, 0, len(pdu) + 1, 1) + pdu)
    hdr = s.recv(7)
    _t, _p, length, _u = struct.unpack(">HHHB", hdr)
    body = b""
    while len(body) < length - 1:
        body += s.recv(length - 1 - len(body))
    return body

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("host")
    ap.add_argument("--port", type=int, default=502)
    ap.add_argument("--reset", action="store_true", help="raise matchReset coil for 6 cycles, then poll")
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()
    s = socket.create_connection((a.host, a.port), timeout=2)
    tid, cycle = 0, 0
    while True:
        tid += 1
        di = txn(s, tid, struct.pack(">BHH", 2, 0, 28))
        hr = txn(s, tid + 1, struct.pack(">BHH", 3, 0, 11))
        regs = struct.unpack(">11H", hr[2:])
        coils = [0] * 13
        coils[0] = cycle % 2  # heartbeat
        if a.reset and cycle < 6:
            coils[1] = 1
        bits = sum(v << i for i, v in enumerate(coils)).to_bytes(2, "little")
        txn(s, tid + 2, struct.pack(">BHHB", 15, 0, 13, 2) + bits)
        print(f"fieldIo=0x{regs[0]:04x} red={regs[1]} blue={regs[2]} "
              f"redSensors={list(regs[3:7])} blueSensors={list(regs[7:11])} "
              f"estop/ftaReady DI bytes={di[2:].hex()}")
        cycle += 1
        if a.once:
            return
        time.sleep(0.1)

if __name__ == "__main__":
    main()
