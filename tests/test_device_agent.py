import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import device_agent


class DeviceAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "device-test.db"
        self.patch = patch.object(device_agent, "DB_PATH", self.db)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def test_pair_token_authenticate_and_revoke(self):
        paired = device_agent.pair_device(17, "Test Android")
        self.assertEqual(paired["device_name"], "Test Android")
        self.assertEqual(
            device_agent.authenticate_device(paired["device_token"])["device_id"],
            paired["device_id"],
        )
        listed = device_agent.list_devices(17)
        self.assertEqual(len(listed), 1)
        self.assertNotIn("token_hash", listed[0])
        self.assertNotIn("device_token", listed[0])

        self.assertTrue(device_agent.revoke_device(17, paired["device_id"]))
        self.assertIsNone(device_agent.authenticate_device(paired["device_token"]))
        self.assertFalse(device_agent.revoke_device(17, paired["device_id"]))

    def test_device_cannot_be_revoked_by_another_account(self):
        paired = device_agent.pair_device(17, "Test Android")
        self.assertFalse(device_agent.revoke_device(99, paired["device_id"]))
        self.assertIsNotNone(device_agent.authenticate_device(paired["device_token"]))

    def test_invalid_tokens_are_rejected(self):
        self.assertIsNone(device_agent.authenticate_device(""))
        self.assertIsNone(device_agent.authenticate_device("x" * 300))


if __name__ == "__main__":
    unittest.main()
