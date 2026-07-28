# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langgraph.config import get_config
from runtime_service.runtime.runtime_request_resolver import resolve_runtime_options

from . import parsing as _parsing
from . import prompting as _prompting
from . import protocol as _protocol
from . import types as _types

AttachmentArtifact = _types.AttachmentArtifact
AttachmentKind = _types.AttachmentKind
AttachmentParser = _types.AttachmentParser
AttachmentStatus = _types.AttachmentStatus
AsyncAttachmentParser = _types.AsyncAttachmentParser
DEFAULT_MULTIMODAL_MODEL_ID = _types.DEFAULT_MULTIMODAL_MODEL_ID
get_default_multimodal_model_id = _types.get_default_multimodal_model_id
MULTIMODAL_ATTACHMENTS_KEY = _types.MULTIMODAL_ATTACHMENTS_KEY
MULTIMODAL_SUMMARY_KEY = _types.MULTIMODAL_SUMMARY_KEY
MultimodalAgentState = _types.MultimodalAgentState
ParserResult = _types.ParserResult


class MultimodalMiddleware(AgentMiddleware[AgentState[Any], Any]):
    state_schema = MultimodalAgentState

    def __init__(
        self,
        *,
        parser_model_id: str | None = None,
        parser: AttachmentParser | None = None,
        async_parser: AsyncAttachmentParser | None = None,
        detail_mode: bool = False,
        detail_text_max_chars: int = 2000,
    ) -> None:
        self._parser_model_id = (
            str(parser_model_id).strip()
            if isinstance(parser_model_id, str) and parser_model_id.strip()
            else get_default_multimodal_model_id()
        )
        self._parser = parser
        self._async_parser = async_parser
        self._detail_mode = detail_mode
        self._detail_text_max_chars = max(0, detail_text_max_chars)

    def _resolve_parser_model_id(self, runtime: Any | None = None) -> str:
        del runtime
        try:
            options = resolve_runtime_options(get_config())
        except RuntimeError:
            return self._parser_model_id
        override = options.multimodal_parser_model_id
        if isinstance(override, str) and override.strip():
            return override.strip()
        return self._parser_model_id

    @staticmethod
    def _new_state(
        messages: Sequence[Any], current_state: Mapping[str, Any] | None = None
    ) -> MultimodalAgentState:
        payload = dict(current_state or {})
        payload["messages"] = list(messages)
        return MultimodalAgentState(**payload)

    @staticmethod
    def _read_state_attachments(
        state: Mapping[str, Any] | None,
    ) -> list[AttachmentArtifact]:
        if state is None:
            return []
        value = state.get(MULTIMODAL_ATTACHMENTS_KEY)
        if not isinstance(value, list):
            return []
        normalized: list[AttachmentArtifact] = []
        required_keys = (
            "attachment_id",
            "kind",
            "status",
            "summary_for_model",
            "provenance",
        )
        for item in value:
            if not isinstance(item, Mapping):
                continue
            if any(key not in item for key in required_keys):
                continue
            normalized.append(AttachmentArtifact(**dict(item)))
        return normalized

    @staticmethod
    def _read_state_summary(state: Mapping[str, Any] | None) -> str | None:
        if state is None:
            return None
        value = state.get(MULTIMODAL_SUMMARY_KEY)
        return value if isinstance(value, str) else None

    @staticmethod
    def _build_state(
        messages: Sequence[Any], current_state: Mapping[str, Any] | None = None
    ) -> MultimodalAgentState:
        state = MultimodalMiddleware._new_state(messages, current_state)
        existing_artifacts = MultimodalMiddleware._read_state_attachments(state)
        current_artifacts = _protocol.collect_current_turn_attachment_artifacts(
            messages,
            start_index=len(existing_artifacts) + 1,
        )
        merged = MultimodalMiddleware._merge_session_artifacts(
            existing_artifacts,
            current_artifacts,
        )
        return _prompting._apply_multimodal_state(state, merged)

    @staticmethod
    def _artifact_fingerprint(artifact: AttachmentArtifact) -> str | None:
        provenance = artifact.get("provenance")
        if not isinstance(provenance, Mapping):
            return None
        value = provenance.get("fingerprint")
        return value if isinstance(value, str) and value.strip() else None

    @staticmethod
    def _merge_session_artifacts(
        existing: Sequence[AttachmentArtifact],
        incoming: Sequence[AttachmentArtifact],
    ) -> list[AttachmentArtifact]:
        merged: list[AttachmentArtifact] = [dict(item) for item in existing]
        seen_fingerprints = {
            fp
            for fp in (
                MultimodalMiddleware._artifact_fingerprint(item) for item in merged
            )
            if fp is not None
        }
        for artifact in incoming:
            fingerprint = MultimodalMiddleware._artifact_fingerprint(artifact)
            if fingerprint is not None and fingerprint in seen_fingerprints:
                continue
            merged.append(dict(artifact))
            if fingerprint is not None:
                seen_fingerprints.add(fingerprint)
        return merged

    def _prepare_artifact_parsing(
        self,
        messages: Sequence[Any], current_state: Mapping[str, Any] | None = None
    ) -> tuple[
        MultimodalAgentState,
        list[tuple[AttachmentArtifact, Mapping[str, Any]]],
        list[tuple[AttachmentArtifact, Mapping[str, Any]]],
    ]:
        state = MultimodalMiddleware._new_state(messages, current_state)
        existing_artifacts = self._read_state_attachments(state)
        context = _protocol._find_latest_human_message_attachment_context(messages)
        if context is None:
            return _prompting._apply_multimodal_state(state, existing_artifacts), [], []
        _, _, content = context
        current_pairs, incoming_artifacts = self._resolve_current_turn_pairs(
            content, existing_artifacts
        )
        merged_artifacts = self._merge_session_artifacts(existing_artifacts, incoming_artifacts)
        _prompting._apply_multimodal_state(state, merged_artifacts)
        parse_pairs: list[tuple[AttachmentArtifact, Mapping[str, Any]]] = []
        seen_attachment_ids: set[str] = set()
        for artifact, block in current_pairs:
            attachment_id = artifact["attachment_id"]
            if attachment_id in seen_attachment_ids:
                continue
            seen_attachment_ids.add(attachment_id)
            if artifact["status"] in {"parsed", "unsupported"}:
                continue
            parse_pairs.append((artifact, block))
        return state, current_pairs, parse_pairs

    @classmethod
    def _resolve_current_turn_pairs(
        cls,
        content: Sequence[Any],
        existing_artifacts: Sequence[AttachmentArtifact],
    ) -> tuple[
        list[tuple[AttachmentArtifact, Mapping[str, Any]]],
        list[AttachmentArtifact],
    ]:
        current_pairs: list[tuple[AttachmentArtifact, Mapping[str, Any]]] = []
        incoming_artifacts: list[AttachmentArtifact] = []
        existing_by_fingerprint: dict[str, AttachmentArtifact] = {}
        for artifact in existing_artifacts:
            fingerprint = cls._artifact_fingerprint(artifact)
            if fingerprint is None or fingerprint in existing_by_fingerprint:
                continue
            existing_by_fingerprint[fingerprint] = artifact

        next_index = len(existing_artifacts) + 1
        for item in content:
            if not isinstance(item, Mapping):
                continue
            candidate = _protocol.build_attachment_artifact(item, next_index)
            if candidate is None:
                continue

            fingerprint = cls._artifact_fingerprint(candidate)
            matched = (
                existing_by_fingerprint.get(fingerprint)
                if fingerprint is not None
                else None
            )
            if matched is not None:
                current_pairs.append((matched, item))
                continue

            incoming_artifacts.append(candidate)
            current_pairs.append((candidate, item))
            if fingerprint is not None:
                existing_by_fingerprint[fingerprint] = candidate
            next_index += 1

        return current_pairs, incoming_artifacts

    def _resolve_rewrite_artifacts(
        self,
        state: Mapping[str, Any] | None,
        current_pairs: Sequence[tuple[AttachmentArtifact, Mapping[str, Any]]],
    ) -> list[AttachmentArtifact]:
        if not current_pairs:
            return []
        state_by_id = {
            artifact["attachment_id"]: artifact
            for artifact in self._read_state_attachments(state)
        }
        return [
            state_by_id.get(artifact["attachment_id"], artifact)
            for artifact, _ in current_pairs
        ]

    def _parse_artifacts(
        self,
        messages: Sequence[Any],
        current_state: Mapping[str, Any] | None = None,
        runtime: Any | None = None,
    ) -> tuple[MultimodalAgentState, list[AttachmentArtifact]]:
        state, current_pairs, parse_pairs = self._prepare_artifact_parsing(messages, current_state)
        if not current_pairs:
            return state, []
        if not parse_pairs:
            return state, self._resolve_rewrite_artifacts(state, current_pairs)

        parser_model_id = self._resolve_parser_model_id(runtime)
        current_state_artifacts = self._read_state_attachments(state)
        existing_by_id = {
            artifact["attachment_id"]: artifact for artifact in current_state_artifacts
        }
        for base_artifact, item in parse_pairs:
            if base_artifact["kind"] not in {"image", "pdf"}:
                parsed = base_artifact
            elif self._parser is not None:
                try:
                    parsed = self._parser(base_artifact, item)
                except Exception as exc:
                    parsed = _parsing._build_failed_artifact(
                        base_artifact,
                        f"附件解析失败：{exc}",
                        model_id=parser_model_id,
                    )
            else:
                parsed = _parsing._parse_attachment_with_model(
                    base_artifact, item, model_id=parser_model_id
                )
            existing_by_id[parsed["attachment_id"]] = parsed
        merged = [existing_by_id[item["attachment_id"]] for item in current_state_artifacts]
        next_state = _prompting._apply_multimodal_state(state, merged)
        return next_state, self._resolve_rewrite_artifacts(next_state, current_pairs)

    async def _aparse_artifacts(
        self,
        messages: Sequence[Any],
        current_state: Mapping[str, Any] | None = None,
        runtime: Any | None = None,
    ) -> tuple[MultimodalAgentState, list[AttachmentArtifact]]:
        state, current_pairs, parse_pairs = self._prepare_artifact_parsing(messages, current_state)
        if not current_pairs:
            return state, []
        if not parse_pairs:
            return state, self._resolve_rewrite_artifacts(state, current_pairs)

        parser_model_id = self._resolve_parser_model_id(runtime)
        current_state_artifacts = self._read_state_attachments(state)
        existing_by_id = {
            artifact["attachment_id"]: artifact for artifact in current_state_artifacts
        }
        for base_artifact, item in parse_pairs:
            if base_artifact["kind"] not in {"image", "pdf"}:
                parsed = base_artifact
            elif self._async_parser is not None:
                try:
                    parsed = await self._async_parser(base_artifact, item)
                except Exception as exc:
                    parsed = _parsing._build_failed_artifact(
                        base_artifact,
                        f"附件解析失败：{exc}",
                        model_id=parser_model_id,
                    )
            elif self._parser is not None:
                try:
                    parsed = self._parser(base_artifact, item)
                except Exception as exc:
                    parsed = _parsing._build_failed_artifact(
                        base_artifact,
                        f"附件解析失败：{exc}",
                        model_id=parser_model_id,
                    )
            else:
                parsed = await _parsing._aparse_attachment_with_model(
                    base_artifact, item, model_id=parser_model_id
                )
            existing_by_id[parsed["attachment_id"]] = parsed
        merged = [existing_by_id[item["attachment_id"]] for item in current_state_artifacts]
        next_state = _prompting._apply_multimodal_state(state, merged)
        return next_state, self._resolve_rewrite_artifacts(next_state, current_pairs)

    def before_model(
        self, state: AgentState[Any], runtime: Any
    ) -> dict[str, Any] | None:
        del runtime
        messages = state.get("messages", [])
        next_state = self._build_state(messages, state)
        updates: dict[str, Any] = {}
        for key in (MULTIMODAL_ATTACHMENTS_KEY, MULTIMODAL_SUMMARY_KEY):
            if state.get(key) != next_state.get(key):
                updates[key] = next_state.get(key)
        return updates or None

    def _augment_request(
        self,
        request: ModelRequest,
        next_state: Mapping[str, Any] | None = None,
        *,
        normalized_messages: Sequence[Any] | None = None,
        rewrite_artifacts: Sequence[AttachmentArtifact] | None = None,
    ) -> ModelRequest:
        resolved_messages = (
            list(normalized_messages)
            if normalized_messages is not None
            else _protocol.normalize_messages(request.messages)
        )
        resolved_state = (
            MultimodalMiddleware._new_state(resolved_messages, next_state)
            if next_state is not None
            else MultimodalMiddleware._build_state(resolved_messages, request.state)
        )
        artifacts_for_rewrite = (
            list(rewrite_artifacts)
            if rewrite_artifacts is not None
            else self._read_state_attachments(resolved_state)
        )
        rewritten_messages = _prompting._rewrite_latest_human_message_for_model(
            resolved_messages,
            artifacts_for_rewrite,
            include_parsed_text=self._detail_mode,
            parsed_text_max_chars=self._detail_text_max_chars,
        )
        summary = (
            _prompting.build_multimodal_summary_with_options(
                self._read_state_attachments(resolved_state),
                include_parsed_text=self._detail_mode,
                parsed_text_max_chars=self._detail_text_max_chars,
            )
            if self._detail_mode
            else self._read_state_summary(resolved_state)
        )
        system_message = _prompting.build_multimodal_system_message(
            request.system_message, summary
        )
        return request.override(
            messages=rewritten_messages,
            state=resolved_state,
            system_message=system_message,
        )

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        normalized_messages = _protocol.normalize_messages(request.messages)
        next_state, rewrite_artifacts = self._parse_artifacts(
            normalized_messages, request.state, request.runtime
        )
        return handler(
            self._augment_request(
                request=request,
                next_state=next_state,
                normalized_messages=normalized_messages,
                rewrite_artifacts=rewrite_artifacts,
            )
        )

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        normalized_messages = _protocol.normalize_messages(request.messages)
        next_state, rewrite_artifacts = await self._aparse_artifacts(
            normalized_messages, request.state, request.runtime
        )
        return await handler(
            self._augment_request(
                request=request,
                next_state=next_state,
                normalized_messages=normalized_messages,
                rewrite_artifacts=rewrite_artifacts,
            )
        )


__all__ = [
    "AttachmentArtifact",
    "AttachmentKind",
    "AttachmentStatus",
    "MULTIMODAL_ATTACHMENTS_KEY",
    "MULTIMODAL_SUMMARY_KEY",
    "DEFAULT_MULTIMODAL_MODEL_ID",
    "get_default_multimodal_model_id",
    "MultimodalAgentState",
    "MultimodalMiddleware",
]
