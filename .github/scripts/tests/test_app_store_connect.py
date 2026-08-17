import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "app_store_connect.py"
SPEC = importlib.util.spec_from_file_location("app_store_connect", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class AppStoreConnectTests(unittest.TestCase):
    def test_converts_der_signature_to_jwt_raw_format(self):
        r = bytes.fromhex("00") + bytes(range(1, 33))
        s = bytes(range(33, 65))
        der = bytes([0x30, 0x45, 0x02, 0x21]) + r + bytes([0x02, 0x20]) + s
        self.assertEqual(MODULE.der_signature_to_raw(der), r[1:] + s)

    def test_base64url_has_no_padding(self):
        self.assertEqual(MODULE.base64url(b"test"), "dGVzdA")


if __name__ == "__main__":
    unittest.main()
