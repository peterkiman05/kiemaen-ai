import unittest

from core.memory_store import ConversationMemoryStore, normalise_database_url


class ConversationMemoryStoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = ConversationMemoryStore("sqlite+aiosqlite:///:memory:")
        self.assertTrue(await self.store.initialize())

    async def asyncTearDown(self):
        await self.store.close()

    async def test_history_is_isolated_between_accounts(self):
        await self.store.save_turn("account:alice", "Hello", "Hello Alice")
        await self.store.save_turn("account:bob", "Hi", "Hello Bob")

        alice = await self.store.get_recent_history("account:alice")
        bob = await self.store.get_recent_history("account:bob")

        self.assertEqual([item["content"] for item in alice], ["Hello", "Hello Alice"])
        self.assertEqual([item["content"] for item in bob], ["Hi", "Hello Bob"])

    async def test_clear_history_only_clears_selected_account(self):
        await self.store.save_turn("account:alice", "Remember this", "I will use this in context")
        await self.store.save_turn("account:bob", "Keep this", "This belongs to Bob")

        deleted = await self.store.clear_history("account:alice")

        self.assertEqual(deleted, 2)
        self.assertEqual(await self.store.get_recent_history("account:alice"), [])
        self.assertEqual(len(await self.store.get_recent_history("account:bob")), 2)

    def test_aiven_ssl_url_is_normalised_for_asyncpg(self):
        url, connect_args = normalise_database_url(
            "postgres://user:secret@db.example:1234/kiemaen?sslmode=require"
        )
        self.assertTrue(url.startswith("postgresql+asyncpg://"))
        self.assertNotIn("sslmode", url)
        self.assertEqual(connect_args.get("ssl"), "require")


if __name__ == "__main__":
    unittest.main()
