"""
K-water HWPX 보고서 생성 MCP 서버
Claude Desktop에서 직접 보고서를 생성할 수 있도록 툴을 제공합니다.

웹 서비스(api.py)와 동일한 DocumentStore, hwpx_renderer를 공유합니다.
storage/json/ 파일을 공유하므로 웹 UI에서도 동일 문서를 확인할 수 있습니다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp import FastMCP

# 웹 서비스와 동일한 store, 변환 함수 재사용
from chat_service import store, _doc_to_blocks_json
from hwpx_renderer import render_hwpx_real

mcp = FastMCP("K-water 보고서 작성")


# ── 1. 보고서 초안 생성 ────────────────────────────────────────────────────────
@mcp.tool()
def create_report_draft(
    title: str,
    report_type: str,
    sections: list[dict],
    author: str = "",
    department: str = "",
) -> dict[str, Any]:
    """
    K-water 보고서 초안을 생성합니다.

    report_type: "기획" | "현황" | "회의" | "행사"
    sections: [{"key": "background", "heading": "추진배경"}, ...]
    """
    doc = store.create_report(
        title=title,
        author=author,
        department=department,
        sections=sections,
    )
    return {
        "document_id": doc.document_id,
        "title": doc.title,
        "report_type": report_type,
        "sections": [{"key": s.key, "heading": s.heading} for s in doc.sections],
        "created_at": doc.created_at,
    }


# ── 2. 섹션 본문 입력 ─────────────────────────────────────────────────────────
@mcp.tool()
def set_section_text(
    document_id: str,
    section_key: str,
    text: str,
) -> dict[str, Any]:
    """
    특정 섹션에 본문을 입력합니다.
    ** ** 으로 볼드, * 로 시작하는 줄은 참고내용(중고딕)으로 처리됩니다.
    """
    doc = store.get(document_id)
    section = next((s for s in doc.sections if s.key == section_key), None)
    if section is None:
        return {"error": f"section_key '{section_key}' not found"}

    section.blocks = [{"type": "paragraph", "text": text}]
    store.save(doc)
    return {
        "document_id": document_id,
        "section_key": section_key,
        "updated_at": doc.updated_at,
    }


# ── 3. 표 추가 ────────────────────────────────────────────────────────────────
@mcp.tool()
def add_simple_table(
    document_id: str,
    section_key: str,
    headers: list[str],
    rows: list[list[str]],
) -> dict[str, Any]:
    """특정 섹션에 표를 추가합니다. 열 너비는 글자 수 기준으로 자동 조절됩니다."""
    doc = store.get(document_id)
    section = next((s for s in doc.sections if s.key == section_key), None)
    if section is None:
        return {"error": f"section_key '{section_key}' not found"}

    section.blocks.append({"type": "simple_table", "headers": headers, "rows": rows})
    store.save(doc)
    return {
        "document_id": document_id,
        "section_key": section_key,
        "table_index": len([b for b in section.blocks if b.get("type") == "simple_table"]) - 1,
        "updated_at": doc.updated_at,
    }


# ── 4. 표 수정 ────────────────────────────────────────────────────────────────
@mcp.tool()
def update_table(
    document_id: str,
    section_key: str,
    table_index: int,
    headers: list[str] | None = None,
    rows: list[list[str]] | None = None,
) -> dict[str, Any]:
    """특정 섹션의 기존 표를 수정합니다. table_index는 해당 섹션에서 표의 순서(0부터 시작)입니다."""
    doc = store.get(document_id)
    section = next((s for s in doc.sections if s.key == section_key), None)
    if section is None:
        return {"error": f"section_key '{section_key}' not found"}

    table_blocks = [b for b in section.blocks if b.get("type") == "simple_table"]
    if table_index < 0 or table_index >= len(table_blocks):
        return {"error": f"table_index {table_index} out of range (표 {len(table_blocks)}개 존재)"}

    target = table_blocks[table_index]
    if headers is not None:
        target["headers"] = headers
    if rows is not None:
        target["rows"] = rows
    store.save(doc)
    return {
        "document_id": document_id,
        "section_key": section_key,
        "table_index": table_index,
        "updated_at": doc.updated_at,
    }


# ── 5. 문서 조회 ──────────────────────────────────────────────────────────────
@mcp.tool()
def get_document(document_id: str) -> dict[str, Any]:
    """현재 문서 구조와 내용을 반환합니다."""
    doc = store.get(document_id)
    return {
        "document_id": doc.document_id,
        "title": doc.title,
        "sections": [
            {
                "key": s.key,
                "heading": s.heading,
                "blocks": s.blocks,
            }
            for s in doc.sections
        ],
        "updated_at": doc.updated_at,
    }


# ── 6. HWPX 파일 생성 ─────────────────────────────────────────────────────────
@mcp.tool()
def render_hwpx(document_id: str) -> dict[str, Any]:
    """
    문서를 K-water 표준서식 HWPX 파일로 생성합니다.
    생성된 파일 경로를 반환합니다.
    """
    doc = store.get(document_id)
    blocks_json = _doc_to_blocks_json(doc)
    file_path = render_hwpx_real(blocks_json)
    p = Path(file_path)
    return {
        "status": "success",
        "document_id": document_id,
        "file_path": str(p),
        "filename": p.name,
        "size_bytes": p.stat().st_size if p.exists() else 0,
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
