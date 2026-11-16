import os, socket, struct, sys, threading
import unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import fuelhub as fh


def make(local="red"):
    return fh.Store(dict(fh.CFG), local)


class StoreTests(unittest.TestCase):
    def test_refractory(self):
        s = make()
        self.assertTrue(s.pulse(0, now=1.000))
        self.assertFalse(s.pulse(0, now=1.010))
        self.assertTrue(s.pulse(0, now=1.040))
        self.assertTrue(s.pulse(1, now=1.011))  # other channel independent

    def test_sizes_and_required_values(self):
        s = make()
        self.assertEqual(len(s.discrete_inputs()), 28)
        self.assertEqual(len(s.holding_registers()), 11)
        di, hr = s.discrete_inputs(), s.holding_registers()
        self.assertTrue(all(di[i] == 1 for i in range(0, 13)))  # E-stops inverted: 1 = not pressed
        self.assertEqual(di[19], 1)  # ftaReady
        self.assertEqual(hr[0] & 0x0F, 0x0F)  # ArmorBlock bits 0-3 required
        self.assertEqual(hr[0], 0x1F)  # + ftaReadyConnected bit 4

    def test_both_hubs_in_one_map(self):
        s = make("red")
        s.pulse(2, now=1.0)
        s.apply_remote({"epoch": 0, "counts": [1, 2, 3, 4], "sensors": [0, 1, 0, 1]})
        hr = s.holding_registers()
        self.assertEqual(hr[1], 1)
        self.assertEqual(hr[2], 10)
        self.assertEqual(hr[3:7], [0, 0, 1, 0])
        self.assertEqual(hr[7:11], [1, 2, 3, 4])

    def test_reset_epoch_blocks_stale(self):
        s = make("red")
        s.apply_remote({"epoch": 0, "counts": [5, 0, 0, 0], "sensors": [0] * 4})
        self.assertEqual(s.reset(), 1)
        self.assertFalse(s.apply_remote({"epoch": 0, "counts": [9, 0, 0, 0], "sensors": [0] * 4}))
        self.assertEqual(s.holding_registers()[2], 0)

    def test_wrap16(self):
        s = make()
        s.counts["red"][0] = 0xFFFF
        s.pulse(0, now=5.0)
        self.assertEqual(s.counts["red"][0], 0)

    def test_reset_rising_edge_only(self):
        s = make()
        edges = [s.write_coil(fh.COIL_MATCH_RESET, 1) for _ in range(6)]
        self.assertEqual(edges, [True] + [False] * 5)


class ModbusTests(unittest.TestCase):
    def setUp(self):
        self.store = make()
        self.srv = fh.Server(("127.0.0.1", 0), fh.Handler)
        self.srv.store = self.store
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.sock = socket.create_connection(self.srv.server_address, timeout=2)

    def tearDown(self):
        self.sock.close()
        self.srv.shutdown()
        self.srv.server_close()

    def txn(self, pdu):
        self.sock.sendall(struct.pack(">HHHB", 1, 0, len(pdu) + 1, 1) + pdu)
        _t, _p, ln, _u = struct.unpack(">HHHB", self.sock.recv(7))
        body = b""
        while len(body) < ln - 1:
            body += self.sock.recv(ln - 1 - len(body))
        return body

    def test_poll_cycle(self):
        r = self.txn(struct.pack(">BHH", 2, 0, 28))
        self.assertEqual(r[0], 2)
        self.assertEqual(r[1], 4)
        r = self.txn(struct.pack(">BHH", 3, 0, 11))
        self.assertEqual(struct.unpack(">11H", r[2:])[0], 0x001F)
        # write 13 coils with matchReset (bit 1) set, six cycles -> a single reset
        self.store.pulse(0, now=1.0)
        for _ in range(6):
            self.txn(struct.pack(">BHHB", 15, 0, 13, 2) + bytes([0b10, 0]))
        self.assertEqual(self.store.epoch, 1)
        self.assertEqual(sum(self.store.counts["red"]), 0)

    def test_out_of_range(self):
        r = self.txn(struct.pack(">BHH", 3, 0, 12))
        self.assertEqual(r, bytes([0x83, 2]))


if __name__ == "__main__":
    unittest.main()
