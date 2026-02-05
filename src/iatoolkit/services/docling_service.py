# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Any
import base64
import logging
import os
import tempfile

from injector import inject

from iatoolkit.common.exceptions import IAToolkitException
from iatoolkit.services.i18n_service import I18nService


@dataclass
class DoclingTextBlock:
    text: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    block_type: str = "text"
    section_title: Optional[str] = None
    meta: dict = field(default_factory=dict)


@dataclass
class DoclingTable:
    markdown: str
    table_json: dict
    page: Optional[int] = None
    title: Optional[str] = None
    meta: dict = field(default_factory=dict)


@dataclass
class DoclingImage:
    content: bytes
    filename: str
    page: Optional[int] = None
    image_index: Optional[int] = None
    caption_text: Optional[str] = None
    caption_source: Optional[str] = None
    meta: dict = field(default_factory=dict)


@dataclass
class DoclingResult:
    text_blocks: List[DoclingTextBlock]
    tables: List[DoclingTable]
    images: List[DoclingImage]
    full_text: str


class DoclingService:
    @inject
    def __init__(self, i18n_service: I18nService):
        self.i18n_service = i18n_service
        self.enabled = os.getenv("DOCLING_ENABLED", "false").strip().lower() in {"1", "true", "yes"}

    def supports(self, filename: str) -> bool:
        if not filename:
            return False
        _, ext = os.path.splitext(filename.lower())
        return ext in {".pdf", ".docx", ".pptx", ".xlsx", ".html", ".htm"}

    def convert(self, filename: str, content: bytes) -> DoclingResult:
        if not self.enabled:
            raise IAToolkitException(
                IAToolkitException.ErrorType.CONFIG_ERROR,
                self.i18n_service.t("errors.services.docling_disabled")
                if self.i18n_service else "Docling is disabled"
            )

        try:
            from docling.document_converter import DocumentConverter
        except Exception as e:
            logging.error(f"Docling import failed: {e}")
            raise IAToolkitException(
                IAToolkitException.ErrorType.CONFIG_ERROR,
                self.i18n_service.t("errors.services.docling_missing")
                if self.i18n_service else "Docling is not available"
            )

        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            converter = DocumentConverter()
            conversion_result = converter.convert(tmp_path)
            doc = conversion_result.document

            markdown = ""
            try:
                markdown = doc.export_to_markdown()
            except Exception:
                markdown = ""

            doc_dict: dict[str, Any] = {}
            try:
                doc_dict = doc.export_to_dict()
            except Exception:
                doc_dict = {}

            text_blocks = self._extract_text_blocks(doc_dict, markdown)
            tables = self._extract_tables(doc_dict)
            images = self._extract_images(doc_dict, filename)

            full_text = markdown or "\n\n".join([block.text for block in text_blocks if block.text])

            return DoclingResult(
                text_blocks=text_blocks,
                tables=tables,
                images=images,
                full_text=full_text
            )
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    def _extract_text_blocks(self, doc_dict: dict, markdown: str) -> List[DoclingTextBlock]:
        if not doc_dict:
            return [DoclingTextBlock(text=markdown)] if markdown else []

        blocks: List[DoclingTextBlock] = []
        for item in self._walk_items(doc_dict):
            if not isinstance(item, dict):
                continue
            item_type = (item.get("type") or item.get("item_type") or "").lower()
            if "text" in item_type or "paragraph" in item_type:
                text = item.get("text") or item.get("content") or ""
                if not text:
                    continue
                blocks.append(DoclingTextBlock(
                    text=text,
                    page_start=item.get("page") or item.get("page_start"),
                    page_end=item.get("page_end") or item.get("page"),
                    block_type="text",
                    section_title=item.get("title") or item.get("section_title"),
                    meta=self._extract_meta(item, exclude_keys={"text", "content"})
                ))

        if not blocks and markdown:
            blocks.append(DoclingTextBlock(text=markdown))

        return blocks

    def _extract_tables(self, doc_dict: dict) -> List[DoclingTable]:
        tables: List[DoclingTable] = []
        for item in self._walk_items(doc_dict):
            if not isinstance(item, dict):
                continue
            item_type = (item.get("type") or item.get("item_type") or "").lower()
            is_table = "table" in item_type or "table" in item
            if not is_table:
                continue

            markdown = (
                item.get("markdown")
                or item.get("md")
                or item.get("text")
                or ""
            )
            tables.append(DoclingTable(
                markdown=markdown,
                table_json=item,
                page=item.get("page") or item.get("page_start"),
                title=item.get("title") or item.get("caption"),
                meta=self._extract_meta(item, exclude_keys={"markdown", "md", "text"})
            ))
        return tables

    def _extract_images(self, doc_dict: dict, filename: str) -> List[DoclingImage]:
        images: List[DoclingImage] = []
        base_name, _ = os.path.splitext(filename)
        image_count = 0

        for item in self._walk_items(doc_dict):
            if not isinstance(item, dict):
                continue
            item_type = (item.get("type") or item.get("item_type") or "").lower()
            if "image" not in item_type and "figure" not in item_type:
                continue

            raw = item.get("data") or item.get("bytes") or item.get("image_bytes")
            if isinstance(raw, str):
                try:
                    content = base64.b64decode(raw)
                except Exception:
                    content = None
            elif isinstance(raw, (bytes, bytearray)):
                content = bytes(raw)
            else:
                content = None

            if not content:
                continue

            image_count += 1
            images.append(DoclingImage(
                content=content,
                filename=f"{base_name}_img_{image_count}.png",
                page=item.get("page") or item.get("page_start"),
                image_index=item.get("image_index") or image_count,
                caption_text=item.get("caption") or item.get("title"),
                caption_source=item.get("caption_source"),
                meta=self._extract_meta(item, exclude_keys={"data", "bytes", "image_bytes"})
            ))

        return images

    def _extract_meta(self, item: dict, exclude_keys: set[str]) -> dict:
        meta = {}
        for key, value in item.items():
            if key in exclude_keys:
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                meta[key] = value
        return meta

    def _walk_items(self, node: Any):
        if isinstance(node, dict):
            yield node
            for value in node.values():
                yield from self._walk_items(value)
        elif isinstance(node, list):
            for value in node:
                yield from self._walk_items(value)
