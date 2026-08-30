from __future__ import annotations

"""遍历多模态 fixtures，并做“前端形状 content block”编码/解码自检。

为什么要有这个脚本？
- 线上/前端传入的多模态内容通常不是“文件路径”，而是类似：
  - 图片：{"type": "image", "mimeType": "image/png", "data": "<base64>", ...}
  - PDF： {"type": "file",  "mimeType": "application/pdf", "data": "<base64>", ...}
- 后端的多模态中间件需要能稳定处理这些 block。

这个脚本做三件事：
1) 从本地文件读取 bytes，并计算 sha256 作为基准。
2) 调用 `file_path_to_frontend_content_block` 把本地文件编码成“前端形状”的 block。
3) 调用 `decode_block_bytes` 再解码回 bytes，校验 sha256 必须一致（保证 round-trip 不丢数据）。

额外输出：
- 对 PDF：调用 `middlewares.multimodal._extract_pdf_text` 抽取文本，打印页数与前 N 字符预览。
- 对图片：输出 data URL 前缀与 payload 长度（便于快速确认 mime/base64 是否合理）。

使用方式（需要在 apps/runtime-service 目录执行，确保可 import runtime_service）：
- `python -m runtime_service.devtools.dump_multimodal_fixtures`
- `python -m runtime_service.devtools.dump_multimodal_fixtures /path/to/dir_or_file --pdf-preview-chars 200`
"""

import argparse
import base64
import hashlib
import mimetypes
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from runtime_service.devtools.multimodal_frontend_compat import (
    decode_block_bytes,
    file_path_to_frontend_content_block,
    image_block_to_data_url,
)
from runtime_service.middlewares.multimodal import _extract_pdf_text


_DEFAULT_EXTS = (".pdf", ".jpeg", ".jpg", ".png", ".webp", ".gif")


def _format_for_console(value: Any, *, ascii_safe: bool) -> str:
    """格式化输出文本。

    背景：
    - 过去为了避免终端编码问题，常用 `encode('ascii','backslashreplace')` 输出，
      这会把中文变成 `\\uXXXX`，人类不易阅读。
    - 大多数现代终端默认 UTF-8，直接输出中文更友好。

    约定：
    - ascii_safe=True：强制转成 ASCII 可打印（中文会变成 \\uXXXX）
    - ascii_safe=False：尽量直接输出原始 Unicode（推荐，便于阅读中文）
    """

    text = str(value)
    if not ascii_safe:
        return text
    return text.encode("ascii", "backslashreplace").decode("ascii")


def _sha256_hex(raw: bytes) -> str:
    # 用 sha256 做 round-trip 校验：编码成 block 再解码回 bytes 后必须完全一致。
    return hashlib.sha256(raw).hexdigest()


def _detect_mime(path: Path) -> str:
    # mimetypes 在部分系统上可能对某些后缀（例如 .webp）不全，做一层兜底映射。
    guessed, _ = mimetypes.guess_type(str(path))
    if guessed:
        return guessed
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "application/pdf"
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(suffix, "")


def _iter_default_fixture_paths() -> list[Path]:
    # 默认 fixtures 目录：runtime_service/test_data
    test_data_dir = Path(__file__).resolve().parents[1] / "test_data"
    if not test_data_dir.exists():
        raise FileNotFoundError(f"Missing fixtures directory: {test_data_dir}")

    paths: list[Path] = []
    for ext in _DEFAULT_EXTS:
        paths.extend(sorted(test_data_dir.glob(f"*{ext}")))
    return sorted({p.resolve() for p in paths}, key=lambda p: p.name)


def _expand_input_paths(values: Sequence[str]) -> list[Path]:
    # 支持：输入若为目录则递归收集指定后缀；若为文件则直接加入。
    paths: list[Path] = []
    for raw in values:
        p = Path(raw)
        if not p.exists():
            raise FileNotFoundError(f"Missing fixture file: {p}")
        if p.is_dir():
            for ext in _DEFAULT_EXTS:
                paths.extend(sorted(p.glob(f"*{ext}")))
        else:
            paths.append(p)
    return sorted({p.resolve() for p in paths}, key=lambda p: p.name)


def _print_file_report(path: Path, *, pdf_preview_chars: int, ascii_safe: bool) -> None:
    # 每个 fixture 的“自检报告”输出。失败会抛异常，由 main 统计 failures。
    raw = path.read_bytes()
    raw_sha = _sha256_hex(raw)
    payload_len = len(base64.b64encode(raw))
    detected_mime = _detect_mime(path)

    print(
        " ".join(
            [
                f"filename={_format_for_console(path.name, ascii_safe=ascii_safe)}",
                f"mime={_format_for_console(detected_mime, ascii_safe=ascii_safe)}",
                f"base64_len={payload_len}",
                f"sha256={raw_sha}",
            ]
        )
    )

    # 关键：把本地文件编码成“前端形状”的 content block（字段名保持与前端一致：mimeType/data/metadata）。
    block = file_path_to_frontend_content_block(path)

    # 再从 block 中解码回 bytes，确保 round-trip 一致。
    decoded = decode_block_bytes(block)
    decoded_sha = _sha256_hex(decoded)
    assert (
        decoded_sha == raw_sha
    ), f"sha256 mismatch after decode: expected={raw_sha} actual={decoded_sha}"

    mime_type = block.get("mimeType") if isinstance(block, Mapping) else None
    if isinstance(mime_type, str) and mime_type == "application/pdf":
        # PDF 的额外校验：尝试抽取文本，帮助确认解析链路是否正常。
        extracted_text, meta = _extract_pdf_text(block)
        page_count = 0
        if isinstance(meta, Mapping):
            try:
                page_count = int(meta.get("page_count") or 0)
            except Exception:
                page_count = 0
        preview = (extracted_text or "")[: max(0, pdf_preview_chars)]
        print(f"pdf_page_count={page_count}")
        print(
            f"pdf_text_preview={_format_for_console(preview, ascii_safe=ascii_safe)}"
        )
        return

    if isinstance(mime_type, str) and mime_type.startswith("image/"):
        # 图片的额外信息：输出 data URL 前缀和 payload 长度，便于手动粘贴到浏览器验证。
        data_url = image_block_to_data_url(block)
        prefix, payload = data_url.split(",", 1)
        print(
            f"image_data_url_prefix={_format_for_console(prefix + ',', ascii_safe=ascii_safe)}"
        )
        print(f"image_payload_len={len(payload)}")
        return


def main(argv: Sequence[str] | None = None) -> int:
    # 约定：返回码 0=全部通过；1=有失败项；2=输入参数/fixtures 不存在。
    parser = argparse.ArgumentParser(
        description=(
            "Self-test multimodal fixtures: encode to frontend blocks and round-trip decode."
        )
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help=(
            "可选：fixture 文件路径或目录。"
            "若不传，则默认使用 runtime_service/test_data 下的 fixtures。"
        ),
    )
    parser.add_argument(
        "--pdf-preview-chars",
        type=int,
        default=200,
        help="打印抽取到的 PDF 文本预览字符数（默认：200）。",
    )
    parser.add_argument(
        "--ascii-safe",
        action="store_true",
        help=(
            "强制使用 ASCII 安全输出（非 ASCII 字符如中文会以 \\uXXXX 形式展示）。"
            "默认：直接输出可读的 Unicode。"
        ),
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    # 尽量让终端输出用 UTF-8，这样中文不会被 Python 因编码不兼容而替换/报错。
    # 兼容：某些环境/重定向可能没有 reconfigure。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    mimetypes.add_type("image/webp", ".webp")

    try:
        if args.paths:
            paths = _expand_input_paths(args.paths)
        else:
            paths = _iter_default_fixture_paths()
    except FileNotFoundError as exc:
        print(_format_for_console(exc, ascii_safe=args.ascii_safe), file=sys.stderr)
        return 2

    if not paths:
        print(
            _format_for_console(
                "No fixtures found. Provide paths or add files under runtime_service/test_data.",
                ascii_safe=args.ascii_safe,
            ),
            file=sys.stderr,
        )
        return 2

    failures = 0
    for path in paths:
        try:
            _print_file_report(
                path,
                pdf_preview_chars=args.pdf_preview_chars,
                ascii_safe=args.ascii_safe,
            )
        except Exception as exc:
            failures += 1
            print(
                _format_for_console(
                    f"ERROR path={path} err={exc.__class__.__name__}: {exc}",
                    ascii_safe=args.ascii_safe,
                ),
                file=sys.stderr,
            )
        finally:
            print("-")

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
