from __future__ import annotations

import json
import unittest
from pathlib import Path


FIXTURE = Path(__file__).parent / "fixtures" / "runtime_integration_characterization.json"


class RuntimeIntegrationCharacterizationTest(unittest.TestCase):
    def test_fixture_is_secret_free_and_covers_formal_surfaces(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        serialized = json.dumps(payload, ensure_ascii=True).lower()

        self.assertEqual(payload["schema"], "platform-runtime-integration/characterization-v1")
        self.assertNotIn("api_key", serialized)
        self.assertNotIn("token", serialized)
        self.assertIn("/api/langgraph/threads/{thread_id}/commands", payload["gateway_allowlist"])
        self.assertIn("/api/langgraph/threads/{thread_id}/stream/events", payload["gateway_allowlist"])
        self.assertEqual(payload["historical_thread"]["compatibility"], "read-only")

    def test_run_fixture_requires_stable_idempotency_boundary(self) -> None:
        run_start = json.loads(FIXTURE.read_text(encoding="utf-8"))["formal_chat"]["run_start"]
        self.assertEqual(run_start["method"], "POST")
        self.assertIn("Idempotency-Key", run_start["required_headers"])
        self.assertNotIn("tools", run_start["body"]["params"])


if __name__ == "__main__":
    unittest.main()
