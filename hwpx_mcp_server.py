from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import uuid4
import json

from fastmcp import FastMCP
from renderer.hwpx_renderer import render_hwpx_real


# =========================
# Paths
# =========================
BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
JSON_DIR = STORAGE_DIR / "json"
HWPX_DIR = STORAGE_DIR / "hwpx"

for d in (STORAGE_DIR, JSON_DIR, HWPX_DIR):
    d.mkdir(parents=True, exist_ok=True)


# =========================
# Schema
# =========================
@dataclass
class ParagraphBlock:
    type: Literal["paragraph"] = "paragraph"
    text: str = ""


@dataclass
class TableCell:
    text: str
    rowspan: int = 1
    colspan: int = 1


@dataclass
class SimpleTableBlock:
    type: Literal["simple_table"] = "simple_table"
    headers: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)


@dataclass
class MergedTableBlock:
    type: Literal["merged_table"] = "merged_table"
    rows: List[List[TableCell]] = field(default_factory=list)


Block = Union[ParagraphBlock, SimpleTableBlock, MergedTableBlock]


@dataclass
class Section:
    key: str
    heading: str
    blocks: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ReportDocument:
    document_id: str
    doc_type: Literal["report"] = "report"
    title: str = "제목 없음"
    meta: Dict[str, Any] = field(default_factory=dict)
    sections: List[Section] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def touch(self) -> None:
        self.updated_at = datetime.now().isoformat()


DEFAULT_SECTIONS = [
    ("background", "1. 추진배경"),
    ("content", "2. 주요내용"),
    ("expected_effect", "3. 기대효과"),
]


# =========================
# Persistence helpers
# =========================
class DocumentStore:
    def __init__(self) -> None:
        self._docs: Dict[str, ReportDocument] = {}
        self._load_existing()

    def _doc_path(self, document_id: str) -> Path:
        return JSON_DIR / f"{document_id}.json"

    def _load_existing(self) -> None:
        for path in JSON_DIR.glob("*.json"):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                doc = self._from_dict(raw)
                self._docs[doc.document_id] = doc
            except Exception:
                # Skip corrupted files for now
                continue

    def _from_dict(self, raw: Dict[str, Any]) -> ReportDocument:
        sections = [Section(**section) for section in raw.get("sections", [])]
        raw = {**raw, "sections": sections}
        return ReportDocument(**raw)

    def _to_dict(self, doc: ReportDocument) -> Dict[str, Any]:
        return {
            "document_id": doc.document_id,
            "doc_type": doc.doc_type,
            "title": doc.title,
            "meta": doc.meta,
            "sections": [asdict(section) for section in doc.sections],
            "created_at": doc.created_at,
            "updated_at": doc.updated_at,
        }

    def save(self, doc: ReportDocument) -> None:
        doc.touch()
        self._docs[doc.document_id] = doc
        self._doc_path(doc.document_id).write_text(
            json.dumps(self._to_dict(doc), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get(self, document_id: str) -> ReportDocument:
        if document_id not in self._docs:
            raise ValueError(f"document_id '{document_id}' not found")
        return self._docs[document_id]

    def create_report(self, title: str, author: str | None = None, department: str | None = None) -> ReportDocument:
        document_id = f"doc_{uuid4().hex[:8]}"
        doc = ReportDocument(
            document_id=document_id,
            title=title,
            meta={
                "author": author or "",
                "department": department or "",
                "date": datetime.now().strftime("%Y-%m-%d"),
            },
            sections=[Section(key=key, heading=heading) for key, heading in DEFAULT_SECTIONS],
        )
        self.save(doc)
        return doc


store = DocumentStore()


# =========================
# Validation helpers
# =========================
def _find_section(doc: ReportDocument, section_key: str) -> Section:
    for section in doc.sections:
        if section.key == section_key:
            return section
    raise ValueError(f"section_key '{section_key}' not found")


def _validate_headers_and_rows(headers: List[str], rows: List[List[str]]) -> None:
    if not headers:
        raise ValueError("headers must not be empty")
    header_len = len(headers)
    for idx, row in enumerate(rows):
        if len(row) != header_len:
            raise ValueError(f"row {idx} length {len(row)} != header length {header_len}")


def _validate_merged_table(rows: List[List[Dict[str, Any]]]) -> None:
    if not rows:
        raise ValueError("merged table rows must not be empty")
    for r_idx, row in enumerate(rows):
        if not row:
            raise ValueError(f"row {r_idx} is empty")
        for c_idx, cell in enumerate(row):
            if "text" not in cell:
                raise ValueError(f"cell ({r_idx}, {c_idx}) requires 'text'")
            if cell.get("rowspan", 1) < 1 or cell.get("colspan", 1) < 1:
                raise ValueError(f"cell ({r_idx}, {c_idx}) rowspan/colspan must be >= 1")


# =========================
# Renderer (stub)
# =========================
class HwpxRenderer:
    """
    1차 버전에서는 실제 HWPX 바이너리 생성 대신,
    디버깅 가능한 JSON 기반 아웃풋을 먼저 저장합니다.

    다음 단계에서 이 자리에 실제 HWPX XML/ZIP 생성 로직을 연결하면 됩니다.
    """

    def render(self, doc: ReportDocument, output_path: Optional[str] = None) -> Path:
        # filename = output_path or str(HWPX_DIR / f"{doc.document_id}.hwpx")
        # target = Path(filename)
        # target.parent.mkdir(parents=True, exist_ok=True)
        target = HWPX_DIR / f"{doc.document_id}.hwpx"
        target.parent.mkdir(parents=True, exist_ok=True)

        # TODO: 실제 HWPX 패키징 로직으로 교체
        payload = {
            "note": "TODO: replace with real HWPX renderer",
            "document": store._to_dict(doc),
        }
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return target


renderer = HwpxRenderer()


# =========================
# MCP server
# =========================
mcp = FastMCP("report-mcp")


@mcp.tool()
def create_report_draft(title: str, author: str = "", department: str = "") -> Dict[str, Any]:
    """보고서 기본 골격을 생성합니다."""
    doc = store.create_report(title=title, author=author, department=department)
    return store._to_dict(doc)


@mcp.tool()
def set_title(document_id: str, title: str) -> Dict[str, Any]:
    """문서 제목을 설정합니다."""
    doc = store.get(document_id)
    doc.title = title
    store.save(doc)
    return {"document_id": document_id, "title": doc.title, "updated_at": doc.updated_at}


@mcp.tool()
def set_section_text(document_id: str, section_key: str, text: str, append: bool = True) -> Dict[str, Any]:
    """특정 섹션에 본문 문단을 추가하거나 덮어씁니다."""
    doc = store.get(document_id)
    section = _find_section(doc, section_key)

    paragraph = asdict(ParagraphBlock(text=text))
    if append:
        section.blocks.append(paragraph)
    else:
        section.blocks = [paragraph]

    store.save(doc)
    return {
        "document_id": document_id,
        "section_key": section_key,
        "block_count": len(section.blocks),
        "updated_at": doc.updated_at,
    }


@mcp.tool()
def add_simple_table(
    document_id: str,
    section_key: str,
    headers: List[str],
    rows: List[List[str]],
) -> Dict[str, Any]:
    """일반 표를 특정 섹션에 추가합니다."""
    _validate_headers_and_rows(headers, rows)
    doc = store.get(document_id)
    section = _find_section(doc, section_key)
    section.blocks.append(asdict(SimpleTableBlock(headers=headers, rows=rows)))
    store.save(doc)
    return {
        "document_id": document_id,
        "section_key": section_key,
        "table_type": "simple_table",
        "row_count": len(rows),
        "updated_at": doc.updated_at,
    }


@mcp.tool()
def add_merged_table(
    document_id: str,
    section_key: str,
    rows: List[List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """병합 셀(rowspan/colspan) 정보를 가진 표를 특정 섹션에 추가합니다."""
    _validate_merged_table(rows)
    doc = store.get(document_id)
    section = _find_section(doc, section_key)
    section.blocks.append({"type": "merged_table", "rows": rows})
    store.save(doc)
    return {
        "document_id": document_id,
        "section_key": section_key,
        "table_type": "merged_table",
        "row_count": len(rows),
        "updated_at": doc.updated_at,
    }


@mcp.tool()
def get_document(document_id: str) -> Dict[str, Any]:
    """현재 문서 JSON 구조를 반환합니다."""
    doc = store.get(document_id)
    return store._to_dict(doc)


# @mcp.tool()
# def render_hwpx(document_id: str, output_path: str = "") -> Dict[str, Any]:
#     """현재 문서를 HWPX 파일로 렌더링합니다. 현재는 stub 파일을 생성합니다."""
#     doc = store.get(document_id)
#     rendered_path = renderer.render(doc, output_path=output_path or None)

#     exists = rendered_path.exists()
#     size = rendered_path.stat().st_size if exists else 0

#     return {
#         "status": "success",
#         "document_id": document_id,
#         "file_path": str(rendered_path),
#         "exists": exists,
#         "size": size,
#         "updated_at": doc.updated_at,
#     }

@mcp.tool()
def render_hwpx(document_id: str) -> dict:
    doc = store.get(document_id)

    # 🔥 JSON → 실제 값 꺼내기
    title = doc.title
    background = doc.sections[0].blocks[0]["text"] if doc.sections[0].blocks else ""
    content = doc.sections[1].blocks[0]["text"] if doc.sections[1].blocks else ""
    expected_effect = doc.sections[2].blocks[0]["text"] if doc.sections[2].blocks else ""

    file_path = render_hwpx_real(
        title=title,
        background=background,
        content=content,
        expected_effect=expected_effect
    )

    p = Path(file_path)

    return {
        "status": "success",
        "document_id": document_id,
        "file_path": file_path,
        "exists": p.exists(),
        "size": p.stat().st_size if p.exists() else 0,
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
