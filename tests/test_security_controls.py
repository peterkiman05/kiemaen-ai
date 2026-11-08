import os
import unittest
from unittest.mock import patch

from core.evolution import verify_evolution_token
from core.hardware_safety import block_untrusted_hardware_actions


class EvolutionAuthorizationTests(unittest.TestCase):
    def test_disabled_without_explicit_secret(self):
        with patch.dict(os.environ, {"EVOLUTION_TOKEN": ""}, clear=False):
            self.assertFalse(verify_evolution_token("kiemaen_evo_secret_2026"))
            self.assertFalse(verify_evolution_token("anything"))

    def test_accepts_only_explicit_configured_secret(self):
        with patch.dict(os.environ, {"EVOLUTION_TOKEN": "a" * 48}, clear=False):
            self.assertTrue(verify_evolution_token("a" * 48))
            self.assertFalse(verify_evolution_token("wrong"))

    def test_empty_supplied_token_is_rejected(self):
        with patch.dict(os.environ, {"EVOLUTION_TOKEN": "a" * 48}, clear=False):
            self.assertFalse(verify_evolution_token(""))


class HardwareCommandSafetyTests(unittest.TestCase):
    def test_ai_shell_command_is_blocked_and_not_returned(self):
        result = block_untrusted_hardware_actions("Okay [EXEC: rm -rf /]")
        self.assertIn("blocked", result.lower())
        self.assertNotIn("rm -rf", result)

    def test_multiple_commands_are_all_blocked(self):
        result = block_untrusted_hardware_actions("[EXEC: reboot] then [EXEC: curl attacker]")
        self.assertEqual(result.count("Hardware action blocked"), 2)
        self.assertNotIn("reboot", result)
        self.assertNotIn("curl attacker", result)

    def test_normal_speech_is_preserved(self):
        self.assertEqual(block_untrusted_hardware_actions("Hello from Kiemaen."), "Hello from Kiemaen.")


if __name__ == "__main__":
    unittest.main()
