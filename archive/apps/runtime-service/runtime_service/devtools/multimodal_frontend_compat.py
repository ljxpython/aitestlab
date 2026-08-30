from __future__ import annotations

"""多模态“前端形状”兼容工具。

这份文件的核心价值是：在没有前端的情况下，在本地构造/复现前端请求中的 content blocks。

在本项目里，用户消息（HumanMessage / API messages）可能是：
- 纯文本："hello"
- 多段内容：[{"type": "text", "text": "..."}, {"type": "image", ...}, {"type": "file", ...}]

其中附件 block 的常见形状：
- 图片（image block）：
  - type: "image"
  - mimeType: "image/png" / "image/jpeg" ...
  - data: base64 字符串
  - metadata: {"name": "xxx.png"}  # 注意：图片这里常见 key 是 name
- PDF（file block）：
  - type: "file"
  - mimeType: "application/pdf"
  - data: base64 字符串
  - metadata: {"filename": "xxx.pdf"}  # 注意：PDF 这里常见 key 是 filename

本文件提供：
- 从本地文件生成上述 block（file_path_to_frontend_content_block）
- 从 block 解码回原始 bytes（decode_block_bytes）
- 生成 image data URL 便于快速肉眼验证（image_block_to_data_url）
- 归一化字段名（normalize_frontend_block_for_backend）
"""

import base64
import mimetypes
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence

from langchain.messages import HumanMessage


def file_path_to_frontend_content_block(path: str | Path) -> dict[str, Any]:
    """把本地文件编码成“前端请求中的附件 content block”。

    注意：这里故意使用 `mimeType`/`data`（而非 snake_case），以贴近前端传输形态。
    """
    file_path = Path(path)
    raw = file_path.read_bytes()
    payload = base64.b64encode(raw).decode("ascii")

    guessed_mime, _ = mimetypes.guess_type(str(file_path))
    mime_type = guessed_mime or ""

    # PDF 在前端一般用 file block 承载。
    if file_path.suffix.lower() == ".pdf" or mime_type == "application/pdf":
        return {
            "type": "file",
            "mimeType": "application/pdf",
            "data": payload,
            "metadata": {"filename": file_path.name},
        }

    # 图片在前端一般用 image block 承载。
    if mime_type.startswith("image/"):
        return {
            "type": "image",
            "mimeType": mime_type,
            "data": payload,
            "metadata": {"name": file_path.name},
        }

    raise ValueError(f"Unsupported attachment type for path: {file_path}")


def build_human_message(
    text: str,
    *,
    blocks: Sequence[Mapping[str, Any]] | None = None,
) -> Any:
    """构造 LangChain 的 HumanMessage。"""
    content: list[Any] = [{"type": "text", "text": text}]
    if blocks:
        content.extend([dict(block) for block in blocks])
    return HumanMessage(content=content)


def build_human_message_from_paths(text: str, paths: Sequence[str | Path]) -> Any:
    """把多个本地路径转成 blocks，并拼到一条 HumanMessage 的 content 里。"""
    blocks = [file_path_to_frontend_content_block(p) for p in paths]
    return build_human_message(text, blocks=blocks)


def decode_block_bytes(block: Mapping[str, Any]) -> bytes:
    """从 content block 中取出 base64 并解码。

    兼容字段：
    - 前端形状：data
    - 后端归一化：base64
    """
    payload = block.get("data") or block.get("base64")
    if not isinstance(payload, str) or not payload.strip():
        raise ValueError("Missing base64 payload in content block.")
    return base64.b64decode(payload)


def image_block_to_data_url(block: Mapping[str, Any]) -> str:
    """把 image block 转成 data URL，方便直接在浏览器打开/验证。"""
    mime_type = block.get("mimeType") or block.get("mime_type")
    if not isinstance(mime_type, str) or not mime_type.strip():
        raise ValueError("Missing mimeType for image content block.")
    payload = block.get("data") or block.get("base64")
    if not isinstance(payload, str) or not payload.strip():
        raise ValueError("Missing base64 payload in image content block.")
    return f"data:{mime_type};base64,{payload}"


def normalize_frontend_block_for_backend(block: Mapping[str, Any]) -> dict[str, Any]:
    """把前端字段名归一化成后端更容易处理的形态。

    目前后端中间件更偏好：
    - base64: str
    - mime_type: str

    但仍保留原字段，避免破坏上游/调试信息。
    """
    normalized: MutableMapping[str, Any] = dict(block)
    if "base64" not in normalized and isinstance(normalized.get("data"), str):
        normalized["base64"] = normalized["data"]
    if "mime_type" not in normalized:
        raw_mime = normalized.get("mimeType") or normalized.get("mime_type")
        if isinstance(raw_mime, str) and raw_mime.strip():
            normalized["mime_type"] = raw_mime.strip()
    return dict(normalized)


__all__ = [
    "file_path_to_frontend_content_block",
    "build_human_message",
    "build_human_message_from_paths",
    "decode_block_bytes",
    "image_block_to_data_url",
    "normalize_frontend_block_for_backend",
]
