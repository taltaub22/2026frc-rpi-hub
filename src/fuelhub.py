#!/usr/bin/env python3
"""
fuelhub.py - REBUILT Fuel hub counter for Raspberry Pi. Emulates the Allen-Bradley PLC that
Cheesy Arena (main branch, plc/plc.go) talks to over Modbus TCP, so Cheesy Arena needs NO changes.

Register map = plc/plc.go of Cheesy Arena main, commit 4ceffb5 (re-verified 2026-11-17). Cheesy Arena polls ONE
address every 100 ms:
  FC2 read 28 discrete inputs from 0 | FC3 read 11 holding registers from 0 | FC15 write 13 coils from 0

Two Pis, one PLC address:
  SERVER Pi (IP 10.0.100.40) serves Modbus for both hubs.  --serve --alliance red --peer <blue Pi ip>
  PEER   Pi (IP 10.0.100.41) counts its hub and sends UDP updates.  --alliance blue --peer <server ip>

Bench test (no Pi): python3 fuelhub.py --serve --alliance red --simulate --port 5020
"""
import argparse
import json
import logging
import random
import socket
import socketserver
import struct
import threading
import time

log = logging.getLogger("fuelhub")

# ---- plc/plc.go map (index = iota order in the source) ----
N_DI, N_HR, N_COIL = 28, 11, 13
DI_ESTOP_FIRST, DI_ESTOP_LAST = 0, 12  # fieldEStop + 6 x (EStop, AStop): INVERTED, false = pressed
DI_CONNECTED_FIRST, DI_FTA_READY = 13, 19  # redConnected1..blueConnected3 = 13..18, ftaReady = 19
DI_HUB_SENSOR = {"red": 20, "blue": 24}  # redHubSensor1..4 = 20..23, blueHubSensor1..4 = 24..27
HR_FIELD_IO = 0
HR_TOTAL = {"red": 1, "blue": 2}
HR_COUNT = {"red": 3, "blue": 7}  # 4 per-sensor counts each
COIL_HEARTBEAT, COIL_MATCH_RESET = 0, 1  # coils 9/10 = hub motors, 11/12 = hub lights (ignored)

CFG = {
    "pins_bcm": [17, 27, 22, 23],  # physical pins 11, 13, 15, 16
    "active_high": False,  # module OUT idles high, pulls low on detection (VERIFY on bench)
    "debounce_s": 0.002,
    "refractory_s": 0.030,
    "modbus_port": 502,  # 502 needs root or CAP_NET_BIND_SERVICE
    "udp_port": 5021,
    "estops_ok": 1,  # 1 = not pressed (inverted inputs). If 0, Cheesy Arena sees E-STOP ACTIVE
    "stations_connected": 1,  # display only (field monitor / team sign)
    "fta_ready": 1,  # only checked if Settings "FTA ready switch" = Required; later: real dead-man button
    # Bits 0-3 (redDs, blueDs, redIoLink, blueIoLink) are REQUIRED to start a match.
    # Bit 4 (ftaReadyConnectedBit, new in 4ceffb5) only drives the FTA badge on the match play page.
    "field_io_connection": 0x001F,
}
ALLIANCES = ("red", "blue")


class Store:
    def __init__(self, cfg, local):
        self.cfg, self.local = cfg, local
        self.remote = "blue" if local == "red" else "red"
        self.lock = threading.Lock()
        self.counts = {a: [0] * 4 for a in ALLIANCES}
        self.sensors = {a: [0] * 4 for a in ALLIANCES}
        self.last_pulse = [0.0] * 4
        self.coils = [0] * N_COIL
        self.epoch = 0
        self.on_reset = None  # callback(epoch) so the server can tell the peer

    # -- local sensor events --
    def pulse(self, ch, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            if now - self.last_pulse[ch] < self.cfg["refractory_s"]:
                return False
            self.last_pulse[ch] = now
            self.counts[self.local][ch] = (self.counts[self.local][ch] + 1) & 0xFFFF
            return True

    def set_sensor(self, ch, level):
        with self.lock:
            self.sensors[self.local][ch] = 1 if level else 0

    # -- remote hub data (server side) --
    def apply_remote(self, msg):
        with self.lock:
            if msg.get("epoch") != self.epoch:
                return False  # stale update from before the last reset
            self.counts[self.remote] = [int(c) & 0xFFFF for c in msg["counts"]][:4]
            self.sensors[self.remote] = [1 if s else 0 for s in msg["sensors"]][:4]
            return True

    def reset(self, epoch=None):
        with self.lock:
            self.counts = {a: [0] * 4 for a in ALLIANCES}
            self.epoch = self.epoch + 1 if epoch is None else epoch
            ep = self.epoch
        log.info("counters reset (epoch %d)", ep)
        return ep

    def write_coil(self, addr, val):  # lock held by caller
        was = self.coils[addr]
        self.coils[addr] = 1 if val else 0
        return addr == COIL_MATCH_RESET and val and not was  # rising edge only

    # -- Modbus views (lock held by caller) --
    def discrete_inputs(self):
        c = self.cfg
        di = [0] * N_DI
        for i in range(DI_ESTOP_FIRST, DI_ESTOP_LAST + 1):
            di[i] = c["estops_ok"]
        for i in range(DI_CONNECTED_FIRST, DI_FTA_READY):
            di[i] = c["stations_connected"]
        di[DI_FTA_READY] = c["fta_ready"]
        for a in ALLIANCES:
            for i in range(4):
                di[DI_HUB_SENSOR[a] + i] = self.sensors[a][i]
        return di

    def holding_registers(self):
        hr = [0] * N_HR
        hr[HR_FIELD_IO] = self.cfg["field_io_connection"]
        for a in ALLIANCES:
            hr[HR_TOTAL[a]] = sum(self.counts[a]) & 0xFFFF
            for i in range(4):
                hr[HR_COUNT[a] + i] = self.counts[a][i]
        return hr


def _bits(vals):
    out = bytearray((len(vals) + 7) // 8)
    for i, v in enumerate(vals):
        if v:
            out[i // 8] |= 1 << (i % 8)
    return bytes(out)


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        store = self.server.store
        while True:
            hdr = self._recv(7)
            if hdr is None:
                return
            tid, _pid, length, unit = struct.unpack(">HHHB", hdr)
            pdu = self._recv(length - 1)
            if pdu is None:
                return
            body = bytes([unit]) + self._process(store, pdu)
            self.request.sendall(struct.pack(">HHH", tid, 0, len(body)) + body)

    def _recv(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.request.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    @staticmethod
    def _exc(fc, code):
        return bytes([fc | 0x80, code])

    def _process(self, store, pdu):
        fc = pdu[0]
        reset_requested = False
        try:
            with store.lock:
                if fc in (1, 2, 3, 4):
                    addr, qty = struct.unpack(">HH", pdu[1:5])
                    table = {1: store.coils, 2: store.discrete_inputs(),
                             3: store.holding_registers(), 4: store.holding_registers()}[fc]
                    if qty < 1 or addr + qty > len(table):
                        return self._exc(fc, 2)
                    vals = table[addr:addr + qty]
                    data = _bits(vals) if fc in (1, 2) else b"".join(struct.pack(">H", v) for v in vals)
                    return bytes([fc, len(data)]) + data
                if fc in (5, 15):
                    if fc == 5:
                        addr, val = struct.unpack(">HH", pdu[1:5])
                        vals, qty = [val == 0xFF00], 1
                    else:
                        addr, qty, _n = struct.unpack(">HHB", pdu[1:6])
                        vals = [(pdu[6 + i // 8] >> (i % 8)) & 1 for i in range(qty)]
                    if addr + qty > N_COIL:
                        return self._exc(fc, 2)
                    for i, v in enumerate(vals):
                        reset_requested |= store.write_coil(addr + i, v)
                    resp = pdu[:5]
                elif fc in (6, 16):
                    resp = pdu[:5]  # holding registers are read-only here; accept and ignore
                else:
                    return self._exc(fc, 1)
        except (struct.error, IndexError):
            return self._exc(fc, 3)
        if reset_requested:  # outside the lock: reset() locks again
            ep = store.reset()
            if store.on_reset:
                store.on_reset(ep)
        return resp


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


# ---- hub <-> hub link (UDP, JSON) ----
def udp_listener(store, port, stop):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("0.0.0.0", port))
    s.settimeout(0.5)
    while not stop.is_set():
        try:
            data, _ = s.recvfrom(2048)
            msg = json.loads(data)
        except (socket.timeout, ValueError):
            continue
        if msg.get("type") == "state":
            store.apply_remote(msg)
        elif msg.get("type") == "reset":  # peer side: server asks us to zero our counters
            if msg["epoch"] != store.epoch:  # send_reset repeats 3x; reset once per epoch
                store.reset(epoch=msg["epoch"])


def udp_sender(store, peer, port, stop, serving):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    while not stop.is_set():
        if not serving:  # peer pushes its counts ~10x/s (also acts as a heartbeat)
            with store.lock:
                msg = {"type": "state", "epoch": store.epoch, "counts": store.counts[store.local],
                       "sensors": store.sensors[store.local]}
            s.sendto(json.dumps(msg).encode(), (peer, port))
        time.sleep(0.1)


def send_reset(peer, port, epoch):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for _ in range(3):  # UDP: repeat; the epoch makes duplicates harmless
        s.sendto(json.dumps({"type": "reset", "epoch": epoch}).encode(), (peer, port))
        time.sleep(0.02)


# ---- GPIO / simulation ----
def start_gpio(store, cfg):
    from gpiozero import DigitalInputDevice  # lazy: --simulate runs anywhere
    devs = []
    for ch, pin in enumerate(cfg["pins_bcm"]):
        d = DigitalInputDevice(pin, pull_up=None, active_state=cfg["active_high"],
                               bounce_time=cfg["debounce_s"])
        d.when_activated = lambda ch=ch: (store.set_sensor(ch, 1), store.pulse(ch))
        d.when_deactivated = lambda ch=ch: store.set_sensor(ch, 0)
        devs.append(d)
    return devs


def simulate(store, stop):
    while not stop.is_set():
        store.pulse(random.randrange(4))
        time.sleep(random.uniform(0.02, 0.2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--alliance", choices=ALLIANCES, required=True, help="which hub this Pi reads")
    ap.add_argument("--serve", action="store_true", help="act as the PLC Cheesy Arena talks to (10.0.100.40)")
    ap.add_argument("--peer", help="IP of the other Pi")
    ap.add_argument("--simulate", action="store_true")
    ap.add_argument("--port", type=int, default=CFG["modbus_port"])
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    store, stop = Store(CFG, args.alliance), threading.Event()
    keep = start_gpio(store, CFG) if not args.simulate else None  # noqa: F841
    if args.simulate:
        threading.Thread(target=simulate, args=(store, stop), daemon=True).start()
    threading.Thread(target=udp_listener, args=(store, CFG["udp_port"], stop), daemon=True).start()
    if args.peer:
        threading.Thread(target=udp_sender, args=(store, args.peer, CFG["udp_port"], stop, args.serve),
                         daemon=True).start()
    if args.serve:
        if args.peer:
            store.on_reset = lambda ep: send_reset(args.peer, CFG["udp_port"], ep)
        srv = Server(("0.0.0.0", args.port), Handler)
        srv.store = store
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        log.info("PLC emulation on Modbus TCP :%d, local hub=%s", args.port, args.alliance)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop.set()


if __name__ == "__main__":
    main()
