import unittest
from core.credential_safety import hash_otp_code, verify_otp_code, hash_session_token

class CredentialSafetyTests(unittest.TestCase):
    def test_otp_is_not_stored_as_plaintext(self):
        code = "012345"
        stored = hash_otp_code(code)
        self.assertNotEqual(stored, code)
        self.assertTrue(verify_otp_code(stored, code))
        self.assertFalse(verify_otp_code(stored, "999999"))

    def test_otp_hashes_use_independent_salts(self):
        self.assertNotEqual(hash_otp_code("123456"), hash_otp_code("123456"))

    def test_legacy_plaintext_otp_remains_valid_until_expiry(self):
        self.assertTrue(verify_otp_code("123456", "123456"))
        self.assertFalse(verify_otp_code("123456", "654321"))

    def test_malformed_hash_is_rejected(self):
        self.assertFalse(verify_otp_code("pbkdf2_sha256$99999999$bad$bad", "123456"))

    def test_session_token_storage_is_one_way_and_deterministic(self):
        token = "session-secret"
        hashed = hash_session_token(token)
        self.assertNotEqual(hashed, token)
        self.assertEqual(hashed, hash_session_token(token))
        self.assertEqual(len(hashed), 64)

if __name__ == "__main__":
    unittest.main()
