from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx
from app.core.errors import PlatformApiError
from app.adapters.langgraph.runs_sdk_adapter import LangGraphRunsSdkAdapter
from app.adapters.langgraph.runtime_client import LangGraphRuntimeClient
from app.adapters.langgraph.runtime_gateway_upstream import LangGraphRuntimeGatewayUpstream
from app.adapters.langgraph.threads_sdk_adapter import LangGraphThreadsSdkAdapter
from app.modules.runtime_gateway.presentation.http import router


async def _collect_chunks(stream):
    chunks: list[bytes] = []
    async for chunk in stream:
        chunks.append(chunk)
    return chunks


async def _stream_events(*events):
    for event in events:
        yield event


class RuntimeGatewaySdkAdaptersTest(unittest.IsolatedAsyncioTestCase):
    async def test_threads_count_wraps_integer_into_count_object(self) -> None:
        fake_client = SimpleNamespace(
            threads=SimpleNamespace(
                count=AsyncMock(return_value=7),
            )
        )
        with patch(
            "app.adapters.langgraph.threads_sdk_adapter.get_langgraph_client",
            return_value=fake_client,
        ):
            adapter = LangGraphThreadsSdkAdapter(base_url="http://example.com")
            payload = await adapter.count({"metadata": {"project_id": "p-1"}})

        self.assertEqual(payload, {"count": 7})

    async def test_runs_stream_encodes_tuple_events_as_sse(self) -> None:
        fake_client = SimpleNamespace(
            runs=SimpleNamespace(
                stream=Mock(
                    return_value=_stream_events(
                        ("values", {"ok": True}, "evt-1"),
                        {"hello": "world"},
                    )
                )
            )
        )
        with patch(
            "app.adapters.langgraph.runs_sdk_adapter.get_langgraph_client",
            return_value=fake_client,
        ):
            adapter = LangGraphRunsSdkAdapter(base_url="http://example.com")
            stream = await adapter.stream_global(
                {"assistant_id": "assistant-1", "version": "v2"}
            )
            chunks = await _collect_chunks(stream)

        body = b"".join(chunks).decode("utf-8")
        fake_client.runs.stream.assert_called_once_with(
            None,
            "assistant-1",
            version="v2",
        )
        self.assertIn("event: values", body)
        self.assertIn('data: {"ok":true}', body)
        self.assertIn("id: evt-1", body)
        self.assertIn('data: {"hello":"world"}', body)

    async def test_runs_join_stream_encodes_events_as_sse(self) -> None:
        fake_client = SimpleNamespace(
            runs=SimpleNamespace(
                join_stream=Mock(
                    return_value=_stream_events(
                        ("tasks", {"current": "step-1"}),
                    )
                )
            )
        )
        with patch(
            "app.adapters.langgraph.runs_sdk_adapter.get_langgraph_client",
            return_value=fake_client,
        ):
            adapter = LangGraphRunsSdkAdapter(base_url="http://example.com")
            stream = await adapter.join_stream("thread-1", "run-1", {"stream_mode": "values"})
            chunks = await _collect_chunks(stream)

        body = b"".join(chunks).decode("utf-8")
        self.assertIn("event: tasks", body)
        self.assertIn('data: {"current":"step-1"}', body)
        fake_client.runs.join_stream.assert_called_once_with(
            "thread-1",
            "run-1",
            stream_mode="values",
            cancel_on_disconnect=False,
        )

    async def test_runs_join_stream_rejects_disconnect_cancellation(self) -> None:
        fake_client = SimpleNamespace(runs=SimpleNamespace(join_stream=Mock()))
        with patch(
            "app.adapters.langgraph.runs_sdk_adapter.get_langgraph_client",
            return_value=fake_client,
        ):
            adapter = LangGraphRunsSdkAdapter(base_url="http://example.com")
            with self.assertRaisesRegex(ValueError, "cancel_on_disconnect=true"):
                await adapter.join_stream(
                    "thread-1",
                    "run-1",
                    {"cancel_on_disconnect": True},
                )

        fake_client.runs.join_stream.assert_not_called()

    async def test_runs_cancel_many_passthrough_none(self) -> None:
        fake_client = SimpleNamespace(
            runs=SimpleNamespace(
                cancel_many=AsyncMock(return_value=None),
            )
        )
        with patch(
            "app.adapters.langgraph.runs_sdk_adapter.get_langgraph_client",
            return_value=fake_client,
        ):
            adapter = LangGraphRunsSdkAdapter(base_url="http://example.com")
            payload = await adapter.cancel_many({"status": "pending"})

        self.assertIsNone(payload)

    async def test_crons_count_wraps_integer_into_count_object(self) -> None:
        fake_client = SimpleNamespace(
            crons=SimpleNamespace(
                count=AsyncMock(return_value=5),
            )
        )
        with patch(
            "app.adapters.langgraph.runs_sdk_adapter.get_langgraph_client",
            return_value=fake_client,
        ):
            adapter = LangGraphRunsSdkAdapter(base_url="http://example.com")
            payload = await adapter.count_crons({"assistant_id": "assistant-1"})

        self.assertEqual(payload, {"count": 5})

    async def test_protocol_v2_upstream_uses_exact_standard_paths(self) -> None:
        upstream = LangGraphRuntimeGatewayUpstream(
            base_url="http://example.com",
            timeout_seconds=1.0,
        )
        stream = object()
        upstream._http = SimpleNamespace(  # type: ignore[assignment]
            request_json=AsyncMock(return_value={"type": "success", "id": 1}),
            stream=AsyncMock(return_value=stream),
        )
        command = {"id": 1, "method": "input.respond", "params": {}}
        subscription = {"channels": ["messages"], "since": 3}

        response = await upstream.send_thread_command("thread-1", command)
        event_stream = await upstream.stream_thread_events("thread-1", subscription)

        self.assertEqual(response, {"type": "success", "id": 1})
        self.assertIs(event_stream, stream)
        upstream._http.request_json.assert_awaited_once_with(  # type: ignore[attr-defined]
            "POST",
            "/threads/thread-1/commands",
            payload=command,
        )
        upstream._http.stream.assert_awaited_once_with(  # type: ignore[attr-defined]
            "POST",
            "/threads/thread-1/stream/events",
            payload=subscription,
        )


class RuntimeGatewayRouterSmokeTest(unittest.TestCase):
    def test_global_run_surface_is_not_public(self) -> None:
        paths = {route.path for route in router.routes}
        self.assertNotIn("/api/langgraph/runs", paths)
        self.assertNotIn("/api/langgraph/runs/cancel", paths)

    def test_chat_allowlist_keeps_thread_run_and_protocol_surfaces(self) -> None:
        paths = {route.path for route in router.routes}
        for path in (
            "/api/langgraph/info",
            "/api/langgraph/graphs/search",
            "/api/langgraph/graphs/count",
            "/api/langgraph/threads",
            "/api/langgraph/threads/search",
            "/api/langgraph/threads/count",
            "/api/langgraph/threads/{thread_id}",
            "/api/langgraph/threads/{thread_id}/state",
            "/api/langgraph/threads/{thread_id}/history",
            "/api/langgraph/threads/{thread_id}/runs",
            "/api/langgraph/threads/{thread_id}/runs/stream",
            "/api/langgraph/threads/{thread_id}/commands",
            "/api/langgraph/threads/{thread_id}/stream/events",
            "/api/langgraph/threads/{thread_id}/runs/{run_id}",
            "/api/langgraph/threads/{thread_id}/runs/{run_id}/join",
            "/api/langgraph/threads/{thread_id}/runs/{run_id}/stream",
            "/api/langgraph/threads/{thread_id}/runs/{run_id}/cancel",
        ):
            self.assertIn(path, paths)


class RuntimeGatewayErrorMappingTest(unittest.IsolatedAsyncioTestCase):
    async def test_runtime_client_raises_platform_api_error_for_upstream_status(self) -> None:
        client = LangGraphRuntimeClient(
            base_url="http://example.com",
            timeout_seconds=1.0,
        )
        response = httpx.Response(
            404,
            json={"detail": "thread missing"},
            request=httpx.Request("GET", "http://example.com/threads/thread-1"),
        )

        with self.assertRaises(PlatformApiError) as ctx:
            await client._raise_for_status(response)

        self.assertEqual(ctx.exception.code, "langgraph_upstream_request_failed")
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.message, "thread missing")
        self.assertEqual(ctx.exception.extra["upstream_status_code"], 404)
        self.assertEqual(ctx.exception.extra["upstream_path"], "/threads/thread-1")


if __name__ == "__main__":
    unittest.main()
