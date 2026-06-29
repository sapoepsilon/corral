#!/usr/bin/env python3
"""End-to-end self-check of the corral CLI against the mock provider — no infra.

Proves the part that would actually break: cap enforcement, the wait signal,
idempotent re-allocate, and that release frees a slot. Run: python3 test_corral.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORRAL = HERE / "corral"

CONFIG = """\
[corral]
state_dir = "{state}"
[provider]
type = "mock"
name_prefix = "t-"
id_min = 900
id_max = 902
[pool]
cap = 2
baseline_id = 100
baseline_ip = "10.0.0.100"
[hooks]
dir = "{hooks}"
"""

SETUP_HOOK = """\
#!/usr/bin/env bash
echo '{"backend_url":"http://mock"}'
"""


class CorralCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        state = Path(self.tmp) / "state"
        hooks = Path(self.tmp) / "hooks"
        hooks.mkdir()
        setup = hooks / "setup-backend"
        setup.write_text(SETUP_HOOK)
        setup.chmod(0o755)
        self.config = Path(self.tmp) / "corral.toml"
        self.config.write_text(CONFIG.format(state=state, hooks=hooks))

    def run_corral(self, *args):
        return subprocess.run(
            [sys.executable, str(CORRAL), "-c", str(self.config), *args],
            capture_output=True, text=True,
        )

    def test_lifecycle(self):
        # fill to cap
        first = self.run_corral("allocate", "a")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(first.stdout)["backend_url"], "http://mock")
        self.assertEqual(self.run_corral("allocate", "b").returncode, 0)

        # at cap -> wait signal (EX_TEMPFAIL)
        third = self.run_corral("allocate", "c")
        self.assertEqual(third.returncode, 75)
        self.assertEqual(json.loads(third.stdout)["status"], "wait")

        # re-allocating an existing key is idempotent, not a new clone
        again = self.run_corral("allocate", "a")
        self.assertEqual(again.returncode, 0)
        self.assertEqual(json.loads(again.stdout)["box_id"], json.loads(first.stdout)["box_id"])

        # release frees a slot
        self.assertEqual(self.run_corral("release", "a").returncode, 0)
        self.assertEqual(self.run_corral("allocate", "c").returncode, 0)

        # shared kind never consumes a clone slot
        shared = self.run_corral("allocate", "x", "--kind", "shared")
        self.assertEqual(shared.returncode, 0)
        self.assertEqual(json.loads(shared.stdout)["ip"], "10.0.0.100")

        listing = json.loads(self.run_corral("list").stdout)
        self.assertEqual(listing["live"], 2)  # b, c


if __name__ == "__main__":
    unittest.main()
