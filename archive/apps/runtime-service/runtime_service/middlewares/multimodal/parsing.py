# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

import base64
import json
import re
import tempfile
from collections.abc import Callable, Mapping
from typing import Any

import pymupdf4llm as _pymupdf4llm
import runtime_service.middlewares.multimodal as multimodal_pkg

try:
    from langchain_community.document_loaders.parsers import LLMImageBlobParser as _LLMImageBlobParser
except Exception:  # pragma: no cover
    _LLMImageBlobParser = None

try:
    from langchain_pymupdf4llm import PyMuPDF4LLMLoader as _PyMuPDF4LLMLoader
except Exception:  # pragma: no cover
    _PyMuPDF4LLMLoader = None

from .protocol import _resolve_mime_type
from .types import (
    AttachmentArtifact,
    AttachmentStatus,
    ParserResult,
)
from runtime_service.runtime.modeling import resolve_model_by_id as _default_resolve_model_by_id


def _copy_attachment_artifact(
    artifact: AttachmentArtifact, **overrides: Any
) -> AttachmentArtifact:
    payload = dict(artifact)
    payload.update(overrides)
    return AttachmentArtifact(**payload)


def _copy_parser_result(parsed: ParserResult, **overrides: Any) -> ParserResult:
    payload = dict(parsed)
    payload.update(overrides)
    return ParserResult(**payload)


def _normalize_pdf_chunks(raw_chunks: Any) -> list[Mapping[str, Any]] | None:
    if not isinstance(raw_chunks, list):
        return None
    chunks: list[Mapping[str, Any]] = []
    for item in raw_chunks:
        if isinstance(item, Mapping):
            chunks.append(item)
    return chunks


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_chunk_source_ref(
    artifact: AttachmentArtifact,
    chunk: Mapping[str, Any],
    *,
    index: int,
) -> dict[str, Any] | None:
    page = chunk.get("page")
    if isinstance(page, int):
        page_number = page
    elif isinstance(page, str) and page.isdigit():
        page_number = int(page)
    else:
        page_number = index + 1
    text = chunk.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    preview = _normalize_whitespace(text)
    if not preview:
        return None
    return {
        "doc_name": artifact.get("name"),
        "kind": artifact.get("kind"),
        "page": page_number,
        "chunk_id": f"p{page_number}_c{index + 1}",
        "preview": preview[:280],
    }


def _build_pdf_source_refs(
    artifact: AttachmentArtifact,
    chunks: list[Mapping[str, Any]],
    *,
    limit: int = 12,
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for idx, chunk in enumerate(chunks):
        ref = _extract_chunk_source_ref(artifact, chunk, index=idx)
        if ref is None:
            continue
        refs.append(ref)
        if len(refs) >= limit:
            break
    return refs


def _ensure_image_source_refs(
    artifact: AttachmentArtifact, parsed: ParserResult
) -> ParserResult:
    structured_data = dict(parsed.get("structured_data") or {})
    source_refs = structured_data.get("source_refs")
    if not isinstance(source_refs, list) or not source_refs:
        structured_data["source_refs"] = [
            {
                "doc_name": artifact.get("name"),
                "kind": artifact.get("kind"),
                "source": "image_block",
            }
        ]
    return _copy_parser_result(
        parsed,
        structured_data=structured_data or None,
    )


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        body = stripped.split("\n", 1)[1] if "\n" in stripped else stripped[3:]
        if body.endswith("```"):
            body = body[:-3]
        return body.strip()
    return stripped


def _extract_json_candidate(text: str) -> str:
    stripped = _strip_code_fence(text)
    match = re.search(r"\{[\s\S]*\}", stripped)
    if match:
        return match.group(0).strip()
    return stripped


def _coerce_confidence(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return 0.0
    if number > 1:
        return 1.0
    return number


def _parse_model_response(raw_text: str) -> ParserResult:
    cleaned = _extract_json_candidate(raw_text)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        fallback_text = _strip_code_fence(raw_text)
        return ParserResult(
            summary_for_model="模型已完成附件解析，但返回内容未能结构化解析。",
            parsed_text=fallback_text[:4000] or None,
            structured_data=None,
            confidence=None,
        )

    if not isinstance(payload, Mapping):
        fallback_text = _strip_code_fence(raw_text)
        return ParserResult(
            summary_for_model="模型已完成附件解析，但返回结构不符合预期。",
            parsed_text=fallback_text[:4000] or None,
            structured_data=None,
            confidence=None,
        )

    summary = payload.get("summary_for_model")
    parsed_text = payload.get("parsed_text")
    structured_data = payload.get("structured_data")
    return ParserResult(
        summary_for_model=(
            str(summary).strip()
            if summary is not None
            else "模型已完成解析，但未返回摘要。"
        ),
        parsed_text=(
            str(parsed_text).strip()
            if isinstance(parsed_text, str) and parsed_text.strip()
            else None
        ),
        structured_data=(
            dict(structured_data) if isinstance(structured_data, Mapping) else None
        ),
        confidence=_coerce_confidence(payload.get("confidence")),
    )


def _build_parser_prompt(artifact: AttachmentArtifact) -> str:
    kind = artifact["kind"]
    name = artifact.get("name") or "未命名附件"
    mime_type = artifact.get("mime_type") or "unknown"
    if kind == "image":
        task = "请分析这张图片，提取可见文字，并给出对后续对话最有价值的简要摘要。"
    elif kind == "pdf":
        task = "请阅读这个 PDF，基于已抽取出的文档文本与结构信息给出简要摘要。"
    else:
        task = "请分析这个文件，并给出对后续对话最有价值的简要摘要。"
    return (
        f"你正在为 LangGraph 多模态中间件做附件预处理。附件名：{name}；类型：{kind}；MIME：{mime_type}。"
        f"{task} 请只返回 JSON，不要返回 Markdown，不要加解释。JSON schema: "
        '{"summary_for_model":"string","parsed_text":"string|null","structured_data":{"key_points":["..."]}|null,"confidence":0.0}'
    )


def _extract_pdf_text_with_chunks(
    block: Mapping[str, Any], *, model_id: str | None = None
) -> tuple[str | None, dict[str, Any] | None, list[Mapping[str, Any]] | None]:
    payload = block.get("base64") or block.get("data")
    if not isinstance(payload, str) or not payload.strip():
        return None, {"page_count": 0, "extraction": "missing_base64"}, None

    try:
        raw_bytes = base64.b64decode(payload)
    except Exception:
        return None, {"page_count": 0, "extraction": "invalid_base64"}, None

    multimodal_available = (
        model_id is not None
        and _PyMuPDF4LLMLoader is not None
        and _LLMImageBlobParser is not None
    )

    page_count: int | None = None
    images_count: int | None = None
    try:
        doc_probe = _pymupdf4llm.pymupdf.open(stream=raw_bytes, filetype="pdf")
        page_count = int(getattr(doc_probe, "page_count", 0) or 0)
        try:
            images_count = 0
            for page in doc_probe:
                images_count += len(page.get_images(full=True))
        except Exception:
            images_count = None
    except Exception:
        return None, {"page_count": 0, "extraction": "document_open_error"}, None
    finally:
        try:
            doc_probe.close()
        except Exception:
            pass

    if multimodal_available:
        resolver = getattr(multimodal_pkg, "resolve_model_by_id", _default_resolve_model_by_id)
        try:
            image_model = resolver(model_id)
            if hasattr(image_model, "bind"):
                image_model = image_model.bind(max_tokens=1024)
        except Exception:
            multimodal_available = False

    if multimodal_available:
        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fp:
                fp.write(raw_bytes)
                fp.flush()
                tmp_path = fp.name

            loader = _PyMuPDF4LLMLoader(
                tmp_path,
                mode="single",
                extract_images=True,
                images_parser=_LLMImageBlobParser(model=image_model),
                table_strategy="lines",
            )
            docs = loader.load()
            if not docs:
                return None, {"page_count": page_count or 0, "extraction": "pymupdf4llm_empty_docs"}, None

            merged_text = "\n\n".join(
                [doc.page_content for doc in docs if isinstance(getattr(doc, "page_content", None), str)]
            ).strip()
            doc_meta: dict[str, Any] = {}
            first_meta = getattr(docs[0], "metadata", None)
            if isinstance(first_meta, Mapping):
                doc_meta.update(first_meta)
            metadata: dict[str, Any] = {
                "page_count": page_count or int(doc_meta.get("total_pages") or 0) or 0,
                "extraction": "langchain_pymupdf4llm_single_multimodal" if merged_text else "langchain_pymupdf4llm_empty_text",
                "images_count": images_count,
                "toc_items": [],
            }
            title = doc_meta.get("title")
            if isinstance(title, str) and title.strip():
                metadata["title"] = title.strip()
            author = doc_meta.get("author")
            if isinstance(author, str) and author.strip():
                metadata["author"] = author.strip()

            chunks = [
                {
                    "page": 1,
                    "text": merged_text,
                    "metadata": doc_meta,
                }
            ]
            return (merged_text or None), metadata, chunks
        except Exception:
            # 回退到纯文本抽取逻辑
            multimodal_available = False
        finally:
            if tmp_path:
                try:
                    import os

                    os.unlink(tmp_path)
                except Exception:
                    pass

    # fallback: 纯文本抽取（不含图片）
    try:
        doc = _pymupdf4llm.pymupdf.open(stream=raw_bytes, filetype="pdf")
    except Exception:
        return None, {"page_count": 0, "extraction": "document_open_error"}, None

    try:
        raw_chunks = _pymupdf4llm.to_markdown(
            doc,
            page_chunks=True,
            ignore_images=True,
            ignore_graphics=False,
            force_text=True,
        )
    except Exception:
        return None, {"page_count": doc.page_count, "extraction": "pymupdf4llm_error"}, None
    finally:
        doc.close()
    chunks = _normalize_pdf_chunks(raw_chunks)
    if chunks is None:
        return None, {"page_count": 0, "extraction": "pymupdf4llm_invalid_output"}, None

    parts: list[str] = []
    total_tables = 0
    total_images = 0
    toc_items: list[Any] = []
    document_metadata: Mapping[str, Any] | None = None
    for chunk in chunks:
        metadata = chunk.get("metadata")
        if document_metadata is None and isinstance(metadata, Mapping):
            document_metadata = metadata
        page_text = chunk.get("text")
        if isinstance(page_text, str) and page_text.strip():
            parts.append(page_text.strip())
        tables = chunk.get("tables")
        if isinstance(tables, list):
            total_tables += len(tables)
        images = chunk.get("images")
        if isinstance(images, list):
            total_images += len(images)
        chunk_toc_items = chunk.get("toc_items")
        if isinstance(chunk_toc_items, list) and chunk_toc_items:
            toc_items.extend(chunk_toc_items)

    text = "\n\n".join(parts).strip()
    page_count = len(chunks)
    metadata = {
        "page_count": page_count,
        "extraction": "pymupdf4llm_markdown" if text else "pymupdf4llm_empty_text",
        "tables_count": total_tables,
        "images_count": total_images,
        "toc_items": toc_items,
    }
    if document_metadata is not None:
        title = document_metadata.get("title")
        if isinstance(title, str) and title.strip():
            metadata["title"] = title.strip()
        author = document_metadata.get("author")
        if isinstance(author, str) and author.strip():
            metadata["author"] = author.strip()
    return (text or None), metadata, chunks


def _extract_pdf_text(
    block: Mapping[str, Any]
) -> tuple[str | None, dict[str, Any] | None]:
    extracted_text, metadata, _ = _extract_pdf_text_with_chunks(block)
    return extracted_text, metadata


def _build_pdf_text_summary_prompt(
    artifact: AttachmentArtifact, extracted_text: str
) -> str:
    name = artifact.get("name") or "未命名 PDF"
    preview = extracted_text[:12000]
    return (
        f"你正在为 LangGraph 多模态中间件总结 PDF 文档。文件名：{name}。"
        "下面是从 PDF 中抽取出的文本，请生成 JSON，不要返回 Markdown，不要加解释。"
        'JSON schema: {"summary_for_model":"string","parsed_text":"string|null","structured_data":{"key_points":["..."]}|null,"confidence":0.0}\n\n'
        f"PDF_TEXT:\n{preview}"
    )


def _phase2_provenance(existing: Any, *, model_id: str) -> dict[str, Any]:
    provenance: dict[str, Any] = {}
    if isinstance(existing, Mapping):
        for key, value in existing.items():
            provenance[str(key)] = value
    provenance["phase"] = "phase2"
    provenance["processor"] = model_id
    return provenance


def _resolve_parser_transport(model_id: str) -> tuple[str, Any, Any]:
    resolver = getattr(multimodal_pkg, "resolve_model_by_id", _default_resolve_model_by_id)
    model = resolver(model_id)
    model_name = getattr(model, "model_name", None)
    root_client = getattr(model, "root_client", None)
    root_async_client = getattr(model, "root_async_client", None)
    if (
        not isinstance(model_name, str)
        or root_client is None
        or root_async_client is None
    ):
        raise ValueError(
            f"Model '{model_id}' is not a ChatOpenAI-compatible parser transport."
        )
    return model_name, root_client, root_async_client


def _extract_openai_response_text(response: Any) -> str:
    def _response_field(name: str) -> Any:
        if hasattr(response, name):
            return getattr(response, name)
        if isinstance(response, Mapping):
            return response.get(name)
        return None

    def _build_malformed_response_error(reason: str) -> ValueError:
        detail_parts = [reason]
        status = _response_field("status")
        if status is not None:
            detail_parts.append(f"status={status}")
        msg = _response_field("msg")
        if msg is not None:
            detail_parts.append(f"msg={msg}")
        body = _response_field("body")
        if body is not None:
            detail_parts.append(f"body={body}")
        raise ValueError("Malformed OpenAI-compatible response: " + "; ".join(detail_parts))

    choices = _response_field("choices")
    if choices is None:
        _build_malformed_response_error("choices is null")
    if not isinstance(choices, list) or not choices:
        _build_malformed_response_error("choices is empty")

    first = choices[0]
    message = getattr(first, "message", None)
    if message is None and isinstance(first, Mapping):
        message = first.get("message")
    if message is None:
        _build_malformed_response_error("first choice has no message")

    content = getattr(message, "content", None)
    if content is None and isinstance(message, Mapping):
        content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, Mapping):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        return "\n".join(parts)
    return str(content)


def _build_image_parser_payload(
    artifact: AttachmentArtifact, block: Mapping[str, Any]
) -> list[dict[str, Any]]:
    mime_type = artifact.get("mime_type") or _resolve_mime_type(block) or "image/png"
    payload = block.get("base64") or block.get("data")
    if not isinstance(payload, str) or not payload.strip():
        raise ValueError("Missing base64 image payload.")
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": _build_parser_prompt(artifact)},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{payload}"},
                },
            ],
        }
    ]


def _build_pdf_summary_payload(
    artifact: AttachmentArtifact, extracted_text: str
) -> list[dict[str, Any]]:
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": _build_pdf_text_summary_prompt(artifact, extracted_text),
                },
            ],
        }
    ]


def _apply_parser_result(
    artifact: AttachmentArtifact, parsed: ParserResult, *, model_id: str
) -> AttachmentArtifact:
    return _copy_attachment_artifact(
        artifact,
        summary_for_model=parsed["summary_for_model"],
        parsed_text=parsed["parsed_text"],
        structured_data=parsed["structured_data"],
        confidence=parsed["confidence"],
        status="parsed",
        provenance=_phase2_provenance(
            artifact.get("provenance"), model_id=model_id
        ),
        error=None,
    )


def _build_failed_artifact(
    artifact: AttachmentArtifact, error_message: str, *, model_id: str
) -> AttachmentArtifact:
    return _copy_attachment_artifact(
        artifact,
        status="failed",
        summary_for_model=error_message,
        provenance=_phase2_provenance(artifact.get("provenance"), model_id=model_id),
        error={"message": error_message},
    )


def _build_failed_artifact_with_context(
    artifact: AttachmentArtifact,
    error_message: str,
    *,
    model_id: str,
    parsed_text: str | None = None,
    structured_data: dict[str, Any] | None = None,
) -> AttachmentArtifact:
    failed = _build_failed_artifact(artifact, error_message, model_id=model_id)
    if parsed_text is not None:
        failed["parsed_text"] = parsed_text
    if structured_data is not None:
        failed["structured_data"] = structured_data
    return failed


def _prepare_pdf_artifact_for_parsing(
    artifact: AttachmentArtifact, block: Mapping[str, Any], *, model_id: str
) -> tuple[
    str | None,
    dict[str, Any] | None,
    list[Mapping[str, Any]] | None,
    AttachmentArtifact | None,
]:
    extracted_text, pdf_meta, pdf_chunks = _extract_pdf_text_with_chunks(
        block, model_id=model_id
    )
    if extracted_text:
        return extracted_text, pdf_meta, pdf_chunks, None
    failed = _build_failed_artifact_with_context(
        artifact,
        "PDF 文本抽取失败或为空，当前解析链路无法继续。",
        model_id=model_id,
        structured_data=pdf_meta,
    )
    return None, pdf_meta, pdf_chunks, failed


def _merge_pdf_parser_result(
    parsed: ParserResult,
    *,
    artifact: AttachmentArtifact,
    extracted_text: str,
    pdf_meta: dict[str, Any] | None,
    pdf_chunks: list[Mapping[str, Any]] | None,
) -> ParserResult:
    next_parsed = dict(parsed)
    structured_data = dict(next_parsed.get("structured_data") or {})
    if pdf_meta is not None:
        structured_data.update(pdf_meta)
    if pdf_chunks:
        structured_data["source_refs"] = _build_pdf_source_refs(artifact, pdf_chunks)
        source_refs = _build_pdf_source_refs(artifact, pdf_chunks)
        structured_data["source_refs"] = source_refs
        structured_data["chunks_preview"] = [
            {
                "chunk_id": ref["chunk_id"],
                "page": ref["page"],
                "preview": ref["preview"],
            }
            for ref in source_refs[:8]
        ]
    parsed_text = next_parsed.get("parsed_text")
    return _copy_parser_result(
        parsed,
        structured_data=structured_data or None,
        parsed_text=parsed_text if parsed_text is not None else extracted_text[:12000],
    )


def _build_pdf_fallback_result(
    artifact: AttachmentArtifact,
    *,
    extracted_text: str,
    pdf_meta: dict[str, Any] | None,
    pdf_chunks: list[Mapping[str, Any]] | None,
    reason: str,
) -> ParserResult:
    name = artifact.get("name") or "未命名 PDF"
    page_count = pdf_meta.get("page_count") if isinstance(pdf_meta, Mapping) else None
    page_part = f"共 {page_count} 页，" if isinstance(page_count, int) and page_count > 0 else ""
    preview = _normalize_whitespace(extracted_text)[:280]
    summary = (
        f"PDF 已完成文本抽取：{name}，{page_part}"
        f"但结构化摘要阶段降级处理（{reason}）。"
        f"请直接基于已抽取文本继续分析。内容预览：{preview}"
    )
    return _merge_pdf_parser_result(
        ParserResult(
            summary_for_model=summary,
            parsed_text=extracted_text[:12000],
            structured_data=dict(pdf_meta or {}),
            confidence=0.35,
        ),
        artifact=artifact,
        extracted_text=extracted_text,
        pdf_meta=pdf_meta,
        pdf_chunks=pdf_chunks,
    )


def _normalize_pdf_summary_failure_reason(exc: Exception) -> str:
    raw = str(exc).strip() or exc.__class__.__name__
    normalized = raw.lower()
    if "setlimitexceeded" in normalized or "toomanyrequests" in normalized or "429" in normalized:
        return (
            "PDF 摘要生成失败：多模态摘要模型当前被限流或额度受限"
            f"（{raw}）"
        )
    return f"PDF 摘要生成失败：{raw}"


def _parse_response_to_artifact(
    artifact: AttachmentArtifact,
    response: Any,
    *,
    model_id: str,
    error_prefix: str,
    parsed_text_on_failure: str | None = None,
    structured_data_on_failure: dict[str, Any] | None = None,
    result_transform: Callable[[ParserResult], ParserResult] | None = None,
    fallback_result: ParserResult | None = None,
) -> AttachmentArtifact:
    try:
        parsed = _parse_model_response(_extract_openai_response_text(response))
    except Exception as exc:
        if fallback_result is not None:
            return _apply_parser_result(artifact, fallback_result, model_id=model_id)
        return _build_failed_artifact_with_context(
            artifact,
            f"{error_prefix}：{exc}",
            model_id=model_id,
            parsed_text=parsed_text_on_failure,
            structured_data=structured_data_on_failure,
        )

    if result_transform is not None:
        parsed = result_transform(parsed)
    return _apply_parser_result(artifact, parsed, model_id=model_id)


def _parse_attachment_with_model(
    artifact: AttachmentArtifact, block: Mapping[str, Any], *, model_id: str
) -> AttachmentArtifact:
    if artifact["kind"] not in {"image", "pdf"}:
        return artifact
    model_name, root_client, _ = _resolve_parser_transport(model_id)
    if artifact["kind"] == "pdf":
        extracted_text, pdf_meta, pdf_chunks, failed = _prepare_pdf_artifact_for_parsing(
            artifact, block, model_id=model_id
        )
        if failed is not None or extracted_text is None:
            return failed if failed is not None else artifact
        try:
            response = root_client.chat.completions.create(
                model=model_name,
                messages=_build_pdf_summary_payload(artifact, extracted_text),
                stream=False,
            )
        except Exception as exc:
            return _apply_parser_result(
                artifact,
                _build_pdf_fallback_result(
                    artifact,
                    extracted_text=extracted_text,
                    pdf_meta=pdf_meta,
                    pdf_chunks=pdf_chunks,
                    reason=_normalize_pdf_summary_failure_reason(exc),
                ),
                model_id=model_id,
            )
        return _parse_response_to_artifact(
            artifact,
            response,
            model_id=model_id,
            error_prefix="PDF 摘要生成失败",
            parsed_text_on_failure=extracted_text[:12000],
            structured_data_on_failure=pdf_meta,
            result_transform=lambda parsed: _merge_pdf_parser_result(
                parsed,
                artifact=artifact,
                extracted_text=extracted_text,
                pdf_meta=pdf_meta,
                pdf_chunks=pdf_chunks,
            ),
            fallback_result=_build_pdf_fallback_result(
                artifact,
                extracted_text=extracted_text,
                pdf_meta=pdf_meta,
                pdf_chunks=pdf_chunks,
                reason="PDF 摘要生成失败",
            ),
        )
    try:
        response = root_client.chat.completions.create(
            model=model_name,
            messages=_build_image_parser_payload(artifact, block),
            stream=False,
        )
    except Exception as exc:
        return _build_failed_artifact(
            artifact, f"附件解析失败：{exc}", model_id=model_id
        )
    return _parse_response_to_artifact(
        artifact,
        response,
        model_id=model_id,
        error_prefix="附件解析失败",
        result_transform=lambda parsed: _ensure_image_source_refs(artifact, parsed),
    )


async def _aparse_attachment_with_model(
    artifact: AttachmentArtifact, block: Mapping[str, Any], *, model_id: str
) -> AttachmentArtifact:
    if artifact["kind"] not in {"image", "pdf"}:
        return artifact
    model_name, _, root_async_client = _resolve_parser_transport(model_id)
    if artifact["kind"] == "pdf":
        extracted_text, pdf_meta, pdf_chunks, failed = _prepare_pdf_artifact_for_parsing(
            artifact, block, model_id=model_id
        )
        if failed is not None or extracted_text is None:
            return failed if failed is not None else artifact
        try:
            response = await root_async_client.chat.completions.create(
                model=model_name,
                messages=_build_pdf_summary_payload(artifact, extracted_text),
                stream=False,
            )
        except Exception as exc:
            return _apply_parser_result(
                artifact,
                _build_pdf_fallback_result(
                    artifact,
                    extracted_text=extracted_text,
                    pdf_meta=pdf_meta,
                    pdf_chunks=pdf_chunks,
                    reason=_normalize_pdf_summary_failure_reason(exc),
                ),
                model_id=model_id,
            )
        return _parse_response_to_artifact(
            artifact,
            response,
            model_id=model_id,
            error_prefix="PDF 摘要生成失败",
            parsed_text_on_failure=extracted_text[:12000],
            structured_data_on_failure=pdf_meta,
            result_transform=lambda parsed: _merge_pdf_parser_result(
                parsed,
                artifact=artifact,
                extracted_text=extracted_text,
                pdf_meta=pdf_meta,
                pdf_chunks=pdf_chunks,
            ),
            fallback_result=_build_pdf_fallback_result(
                artifact,
                extracted_text=extracted_text,
                pdf_meta=pdf_meta,
                pdf_chunks=pdf_chunks,
                reason="PDF 摘要生成失败",
            ),
        )
    try:
        response = await root_async_client.chat.completions.create(
            model=model_name,
            messages=_build_image_parser_payload(artifact, block),
            stream=False,
        )
    except Exception as exc:
        return _build_failed_artifact(
            artifact, f"附件解析失败：{exc}", model_id=model_id
        )
    return _parse_response_to_artifact(
        artifact,
        response,
        model_id=model_id,
        error_prefix="附件解析失败",
        result_transform=lambda parsed: _ensure_image_source_refs(artifact, parsed),
    )
