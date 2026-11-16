import base64, os, subprocess, sys, tempfile, unittest
ROOT = os.path.join(os.path.dirname(__file__), "..")
GEN = os.path.join(ROOT, "provision", "make_sd_config.py")
try:
    import yaml
except ImportError:  # PyYAML is only needed by this test, not by the repo's tools
    yaml = None


@unittest.skipIf(yaml is None, "PyYAML not installed")
class CloudInitTests(unittest.TestCase):
    def gen(self, role):
        d = tempfile.mkdtemp()
        key = os.path.join(d, "k.pub")
        open(key, "w").write("ssh-ed25519 AAAAC3Nza-test tester@laptop\n")
        subprocess.check_call([sys.executable, GEN, role, "--out", d, "--ssh-key-file", key], stdout=subprocess.DEVNULL)
        load = lambda n: yaml.safe_load(open(os.path.join(d, n)))
        return d, load("user-data"), load("network-config"), load("meta-data")

    def test_server(self):
        d, ud, nc, md = self.gen("server")
        self.assertTrue(open(os.path.join(d, "user-data")).read().startswith("#cloud-config\n"))
        self.assertEqual(ud["hostname"], "fuelhub-red")
        self.assertEqual(ud["users"][0]["ssh_authorized_keys"], ["ssh-ed25519 AAAAC3Nza-test tester@laptop"])
        self.assertFalse(ud["ssh_pwauth"])
        self.assertTrue(ud["enable_ssh"])
        eth = nc["network"]["ethernets"]["eth0"]
        self.assertEqual(eth["addresses"], ["10.0.100.40/24"])
        self.assertEqual(eth["routes"][0]["via"], "10.0.100.1")
        files = {f["path"]: base64.b64decode(f["content"]) for f in ud["write_files"]}
        unit = files["/etc/systemd/system/fuelhub.service"].decode()
        self.assertIn("--serve --alliance red --peer 10.0.100.41", unit)
        self.assertIn("/opt/fuelhub/current/fuelhub.py", unit)
        self.assertIn(b"SERVE=1", files["/etc/fuelhub/role.env"])
        self.assertTrue(md["instance_id"].startswith("fuelhub-server-"))

    def test_peer(self):
        d, ud, nc, md = self.gen("peer")
        self.assertEqual(ud["hostname"], "fuelhub-blue")
        self.assertEqual(nc["network"]["ethernets"]["eth0"]["addresses"], ["10.0.100.41/24"])
        files = {f["path"]: base64.b64decode(f["content"]) for f in ud["write_files"]}
        unit = files["/etc/systemd/system/fuelhub.service"].decode()
        self.assertNotIn("--serve", unit)
        self.assertIn("--alliance blue --peer 10.0.100.40", unit)

    def test_seed_installs_with_apply(self):
        """The embedded seed release must pass the real fuelhub-apply (checksum, compile, switch)."""
        d, ud, _, _ = self.gen("server")
        files = {f["path"]: base64.b64decode(f["content"]) for f in ud["write_files"]}
        t = tempfile.mkdtemp()
        for name in ("seed.tar.gz", "seed.tar.gz.sha256"):
            open(os.path.join(t, name), "wb").write(files["/var/lib/fuelhub/" + name])
        open(os.path.join(t, "apply"), "wb").write(files["/usr/local/sbin/fuelhub-apply"])
        env = dict(os.environ, FUELHUB_ROOT=os.path.join(t, "opt"), FUELHUB_ENV=os.path.join(t, "none"),
                   FUELHUB_STATUS=os.path.join(t, "none.json"), NO_SERVICE="1")
        subprocess.check_call(["bash", os.path.join(t, "apply"), os.path.join(t, "seed.tar.gz")], env=env,
                              stdout=subprocess.DEVNULL)
        self.assertTrue(os.path.exists(os.path.join(t, "opt", "current", "fuelhub.py")))

    def test_rejects_private_key(self):
        d = tempfile.mkdtemp(); key = os.path.join(d, "k")
        open(key, "w").write("-----BEGIN OPENSSH PRIVATE KEY-----\nxxx\n")
        r = subprocess.run([sys.executable, GEN, "server", "--out", d, "--ssh-key-file", key],
                           capture_output=True)
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
