from __future__ import annotations

import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.context.models import ActorContext, PlatformRequestContext, ProjectContext, RequestContext, TenantContext
from app.core.errors import PlatformApiError
from app.adapters.langgraph.runs_sdk_adapter import LangGraphRunsSdkAdapter
from app.adapters.langgraph.runtime_client import LangGraphRuntimeClient
from app.adapters.langgraph.runtime_gateway_upstream import LangGraphRuntimeGatewayUpstream
from app.adapters.langgraph.threads_sdk_adapter import LangGraphThreadsSdkAdapter
from app.entrypoints.http.dependencies import get_actor_context
from app.modules.runtime_gateway.presentation.http import get_runtime_gateway_service, router


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
            stream = await adapter.stream_global({"assistant_id": "assistant-1"})
            chunks = await _collect_chunks(stream)

        body = b"".join(chunks).decode("utf-8")
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
    def test_cancel_route_normalizes_none_to_ack(self) -> None:
        project_id = "05077df4-3cb6-4266-ac0a-def112643292"
        actor = ActorContext(
            user_id="user-1",
            platform_roles=("platform_super_admin",),
            project_roles={project_id: ("project_admin",)},
        )

        class _FakeService:
            async def cancel_runs(self, *, actor, project_id, payload):  # type: ignore[no-untyped-def]
                return None

        app = FastAPI()

        @app.middleware("http")
        async def inject_platform_context(request, call_next):  # type: ignore[no-untyped-def]
            request.state.request_id = "test-request"
            request.state.platform_context = PlatformRequestContext(
                request=RequestContext(
                    request_id="test-request",
                    trace_id="test-trace",
                    method=request.method,
                    path=request.url.path,
                    started_at=time.time(),
                ),
                tenant=TenantContext(tenant_id=None),
                project=ProjectContext(project_id=project_id, requested_by_header=True),
                actor=actor,
            )
            return await call_next(request)

        app.dependency_overrides[get_actor_context] = lambda: actor
        app.dependency_overrides[get_runtime_gateway_service] = lambda: _FakeService()
        app.include_router(router)

        client = TestClient(app)
        response = client.post("/api/langgraph/runs/cancel", json={"status": "pending"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})


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
