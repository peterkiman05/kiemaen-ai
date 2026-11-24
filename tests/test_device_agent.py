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

    def test_pair_tokens_are_separate_and_revocation_disables_both(self):
        paired = device_agent.pair_device(17, "Test Android")
        self.assertEqual(paired["device_name"], "Test Android")
        self.assertNotEqual(paired["device_token"], paired["command_token"])
        self.assertEqual(
            device_agent.authenticate_device(paired["device_token"])["device_id"],
            paired["device_id"],
        )
        self.assertIsNone(device_agent.authenticate_command_device(paired["device_token"]))
        self.assertIsNone(device_agent.authenticate_device(paired["command_token"]))
        self.assertEqual(
            device_agent.authenticate_command_device(paired["command_token"])["device_id"],
            paired["device_id"],
        )
        listed = device_agent.list_devices(17)
        self.assertEqual(len(listed), 1)
        self.assertTrue(listed[0]["commands_enabled"])
        self.assertNotIn("token_hash", listed[0])
        self.assertNotIn("command_token_hash", listed[0])
        self.assertNotIn("device_token", listed[0])

        self.assertTrue(device_agent.revoke_device(17, paired["device_id"]))
        self.assertIsNone(device_agent.authenticate_device(paired["device_token"]))
        self.assertIsNone(device_agent.authenticate_command_device(paired["command_token"]))
        self.assertFalse(device_agent.revoke_device(17, paired["device_id"]))

    def test_device_cannot_be_revoked_or_commanded_by_another_account(self):
        paired = device_agent.pair_device(17, "Test Android")
        self.assertFalse(device_agent.revoke_device(99, paired["device_id"]))
        self.assertIsNotNone(device_agent.authenticate_device(paired["device_token"]))
        self.assertIsNone(device_agent.command_device_for_user(99))

    def test_command_queue_claim_and_one_time_result(self):
        paired = device_agent.pair_device(17, "Test Android")
        queued = device_agent.enqueue_command(17, "set_alarm", {"hour": 5, "minute": 30})
        self.assertIsNotNone(queued)
        command = device_agent.claim_next_command(paired["command_token"])
        self.assertEqual(command["command_id"], queued["command_id"])
        self.assertEqual(command["action"], "set_alarm")
        self.assertEqual(command["payload"], {"hour": 5, "minute": 30, "label": "Kiemaen alarm"})
        self.assertIsNone(device_agent.claim_next_command(paired["command_token"]))
        self.assertTrue(device_agent.report_command(
            paired["command_token"], queued["command_id"], "completed", "Alarm handed to Clock."
        ))
        self.assertFalse(device_agent.report_command(
            paired["command_token"], queued["command_id"], "completed", "Replay."
        ))

    def test_command_queue_is_account_and_device_scoped(self):
        first = device_agent.pair_device(17, "First phone")
        second = device_agent.pair_device(22, "Second phone")
        queued = device_agent.enqueue_command(17, "open_app", {"app_name": "WhatsApp"})
        self.assertEqual(queued["device_id"], first["device_id"])
        self.assertIsNone(device_agent.claim_next_command(second["command_token"]))
        command = device_agent.claim_next_command(first["command_token"])
        self.assertEqual(command["payload"], {"app_name": "WhatsApp"})

    def test_revocation_cancels_pending_commands(self):
        paired = device_agent.pair_device(17, "Test Android")
        device_agent.enqueue_command(17, "open_app", {"app_name": "YouTube"})
        self.assertTrue(device_agent.revoke_device(17, paired["device_id"]))
        self.assertIsNone(device_agent.claim_next_command(paired["command_token"]))

    def test_expired_commands_are_not_delivered(self):
        paired = device_agent.pair_device(17, "Test Android")
        queued = device_agent.enqueue_command(17, "open_app", {"app_name": "YouTube"})
        conn = device_agent._connect()
        try:
            conn.execute(
                "UPDATE device_commands SET expires_at=? WHERE command_id=?",
                ("2000-01-01T00:00:00+00:00", queued["command_id"]),
            )
        finally:
            conn.close()
        self.assertIsNone(device_agent.claim_next_command(paired["command_token"]))

    def test_action_payloads_are_strictly_validated(self):
        device_agent.pair_device(17, "Test Android")
        with self.assertRaises(ValueError):
            device_agent.enqueue_command(17, "run_shell", {"command": "rm -rf /"})
        with self.assertRaises(ValueError):
            device_agent.enqueue_command(17, "set_alarm", {"hour": 25, "minute": 0})
        with self.assertRaises(ValueError):
            device_agent.enqueue_command(17, "open_app", {"app_name": "x" * 100})

    def test_parse_supported_commands_only(self):
        self.assertEqual(
            device_agent.parse_device_command("Set an alarm for 5:30 pm tomorrow"),
            ("set_alarm", {"hour": 17, "minute": 30}),
        )
        self.assertEqual(
            device_agent.parse_device_command("open WhatsApp"),
            ("open_app", {"app_name": "WhatsApp"}),
        )
        self.assertEqual(
            device_agent.parse_device_command("open my YouTube"),
            ("open_app", {"app_name": "YouTube"}),
        )
        self.assertIsNone(device_agent.parse_device_command("delete my messages"))
        self.assertIsNone(device_agent.parse_device_command("set an alarm for 25:90"))

    def test_invalid_tokens_are_rejected(self):
        self.assertIsNone(device_agent.authenticate_device(""))
        self.assertIsNone(device_agent.authenticate_device("x" * 300))
        self.assertIsNone(device_agent.authenticate_command_device("x" * 300))


if __name__ == "__main__":
    unittest.main()
