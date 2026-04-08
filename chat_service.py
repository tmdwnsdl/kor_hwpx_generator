from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from dotenv import load_dotenv
load_dotenv()

import openai

from hwpx_renderer import render_hwpx_real

# ── Storage paths ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
JSON_DIR = STORAGE_DIR / "json"
HWPX_DIR = STORAGE_DIR / "hwpx"
for _d in (STORAGE_DIR, JSON_DIR, HWPX_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# ── Document model ─────────────────────────────────────────────────────────────
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


# ── Document store ─────────────────────────────────────────────────────────────
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
                self._docs[raw["document_id"]] = self._from_dict(raw)
            except Exception:
                continue

    def _from_dict(self, raw: dict) -> ReportDocument:
        sections = [Section(**s) for s in raw.get("sections", [])]
        return ReportDocument(**{**raw, "sections": sections})

    def to_dict(self, doc: ReportDocument) -> dict:
        return {
            "document_id": doc.document_id,
            "doc_type": doc.doc_type,
            "title": doc.title,
            "meta": doc.meta,
            "sections": [asdict(s) for s in doc.sections],
            "created_at": doc.created_at,
            "updated_at": doc.updated_at,
        }

    def save(self, doc: ReportDocument) -> None:
        doc.touch()
        self._docs[doc.document_id] = doc
        self._doc_path(doc.document_id).write_text(
            json.dumps(self.to_dict(doc), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get(self, document_id: str) -> ReportDocument:
        # Always reload from file to stay in sync with MCP server
        path = self._doc_path(document_id)
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                self._docs[document_id] = self._from_dict(raw)
            except Exception:
                pass
        if document_id not in self._docs:
            raise ValueError(f"document_id '{document_id}' not found")
        return self._docs[document_id]

    def create_report(
        self, title: str, author: str = "", department: str = ""
    ) -> ReportDocument:
        document_id = f"doc_{uuid4().hex[:8]}"
        doc = ReportDocument(
            document_id=document_id,
            title=title,
            meta={
                "author": author,
                "department": department,
                "date": datetime.now().strftime("%Y-%m-%d"),
            },
            sections=[
                Section(key=key, heading=heading)
                for key, heading in DEFAULT_SECTIONS
            ],
        )
        self.save(doc)
        return doc


store = DocumentStore()


# ── HWPX conversion ────────────────────────────────────────────────────────────
def _doc_to_blocks_json(doc: ReportDocument) -> dict:
    """DocumentStore 형식 → hwpx_renderer가 요구하는 blocks 형식 변환"""
    blocks: List[dict] = []
    for section in doc.sections:
        blocks.append({"type": "heading", "text": section.heading, "level": 2})
        for block in section.blocks:
            btype = block.get("type")
            if btype == "paragraph":
                blocks.append({"type": "paragraph", "text": block.get("text", "")})
            elif btype == "simple_table":
                blocks.append(
                    {
                        "type": "table",
                        "headers": block.get("headers", []),
                        "rows": block.get("rows", []),
                    }
                )
    return {"title": doc.title, "blocks": blocks}


# ── Tool definitions ───────────────────────────────────────────────────────────
TOOLS: List[dict] = [
    {
        "type": "function",
        "function": {
            "name": "create_report_draft",
            "description": "새 보고서 초안을 생성합니다. 보고서 작성을 시작할 때 가장 먼저 호출하세요.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "보고서 제목"},
                    "author": {"type": "string", "description": "작성자 이름 (선택)"},
                    "department": {"type": "string", "description": "부서명 (선택)"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_section_text",
            "description": (
                "특정 섹션에 본문 내용을 입력합니다. "
                "append=false(기본값)이면 기존 내용을 교체하고, true이면 추가합니다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {"type": "string"},
                    "section_key": {
                        "type": "string",
                        "enum": ["background", "content", "expected_effect"],
                        "description": (
                            "background: 추진배경  |  "
                            "content: 주요내용  |  "
                            "expected_effect: 기대효과"
                        ),
                    },
                    "text": {"type": "string", "description": "섹션 본문 내용"},
                    "append": {
                        "type": "boolean",
                        "description": "true=추가, false=교체 (기본값: false)",
                    },
                },
                "required": ["document_id", "section_key", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_simple_table",
            "description": "특정 섹션에 표를 추가합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {"type": "string"},
                    "section_key": {
                        "type": "string",
                        "enum": ["background", "content", "expected_effect"],
                    },
                    "headers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "표 헤더 목록 (예: ['항목', '내용', '비고'])",
                    },
                    "rows": {
                        "type": "array",
                        "items": {"type": "array", "items": {"type": "string"}},
                        "description": "표 데이터 행 목록",
                    },
                },
                "required": ["document_id", "section_key", "headers", "rows"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_document",
            "description": "현재 문서의 전체 내용을 조회합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {"type": "string"},
                },
                "required": ["document_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "render_hwpx",
            "description": "문서를 HWPX 파일로 변환합니다. 보고서 작성이 완료되면 호출하세요.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {"type": "string"},
                },
                "required": ["document_id"],
            },
        },
    },
]


# ── Tool executor ──────────────────────────────────────────────────────────────
def _execute_tool(name: str, inputs: dict) -> dict:
    try:
        if name == "create_report_draft":
            doc = store.create_report(
                title=inputs["title"],
                author=inputs.get("author", ""),
                department=inputs.get("department", ""),
            )
            return store.to_dict(doc)

        elif name == "set_section_text":
            doc = store.get(inputs["document_id"])
            section = next(
                (s for s in doc.sections if s.key == inputs["section_key"]), None
            )
            if section is None:
                return {"error": f"section_key '{inputs['section_key']}' not found"}
            paragraph = {"type": "paragraph", "text": inputs["text"]}
            if inputs.get("append", False):
                section.blocks.append(paragraph)
            else:
                section.blocks = [paragraph]
            store.save(doc)
            return {
                "document_id": inputs["document_id"],
                "section_key": inputs["section_key"],
                "block_count": len(section.blocks),
                "updated_at": doc.updated_at,
            }

        elif name == "add_simple_table":
            doc = store.get(inputs["document_id"])
            section = next(
                (s for s in doc.sections if s.key == inputs["section_key"]), None
            )
            if section is None:
                return {"error": f"section_key '{inputs['section_key']}' not found"}
            section.blocks.append(
                {
                    "type": "simple_table",
                    "headers": inputs["headers"],
                    "rows": inputs["rows"],
                }
            )
            store.save(doc)
            return {
                "document_id": inputs["document_id"],
                "section_key": inputs["section_key"],
                "row_count": len(inputs["rows"]),
                "updated_at": doc.updated_at,
            }

        elif name == "get_document":
            doc = store.get(inputs["document_id"])
            return store.to_dict(doc)

        elif name == "render_hwpx":
            doc = store.get(inputs["document_id"])
            blocks_json = _doc_to_blocks_json(doc)
            file_path = render_hwpx_real(blocks_json)
            p = Path(file_path)
            return {
                "status": "success",
                "document_id": inputs["document_id"],
                "filename": p.name,
                "download_url": f"/download-hwpx/{p.name}",
            }

        else:
            return {"error": f"Unknown tool: {name}"}

    except Exception as exc:
        return {"error": str(exc)}


# ── System prompt ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """당신은 한국 공공기관 및 기업의 공식 보고서 작성을 전문으로 돕는 어시스턴트입니다.
사용자와 대화하며 HWPX 형식의 보고서를 함께 완성합니다.

보고서 구조 (3개 섹션 고정):
  - 1. 추진배경 (section_key: background)  — 사업 배경, 현황, 필요성
  - 2. 주요내용 (section_key: content)     — 구체적 추진 내용, 계획, 방법론
  - 3. 기대효과 (section_key: expected_effect) — 예상 성과, 효과, 파급력

작업 흐름:
  1. 사용자 요청을 파악 → create_report_draft 호출 (문서 초안 생성)
  2. 각 섹션 내용을 사용자와 협의하며 set_section_text로 입력 (append=false로 교체)
  3. 표가 필요하면 add_simple_table 호출
  4. 내용이 모두 완성되면 render_hwpx 호출 → HWPX 파일 생성
  5. 생성 완료 후 다운로드 링크 안내

글쓰기 원칙:
  - 공식적이고 명확한 문체 사용
  - 수치·사실 기반의 구체적 서술
  - 사용자가 제공한 정보를 최대한 반영
  - 부족한 정보는 사용자에게 질문하여 보완"""


# ── Session management ─────────────────────────────────────────────────────────
_sessions: Dict[str, List[dict]] = {}
_session_docs: Dict[str, Optional[str]] = {}


def chat(session_id: str, user_message: str) -> dict:
    """
    사용자 메시지를 처리하고 Claude 응답을 반환합니다.

    Returns:
        {
            "reply": str,
            "session_id": str,
            "document_id": str | None,
            "document_json": dict | None,
            "hwpx_url": str | None,
        }
    """
    if session_id not in _sessions:
        # 첫 메시지 앞에 system prompt 삽입
        _sessions[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
        _session_docs[session_id] = None

    messages = _sessions[session_id]
    messages.append({"role": "user", "content": user_message})

    client = openai.OpenAI()
    hwpx_url: Optional[str] = None

    # Agentic loop
    while True:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=TOOLS,
        )

        msg = response.choices[0].message

        # assistant 메시지를 dict로 변환해 히스토리에 추가
        assistant_entry: dict = {"role": "assistant", "content": msg.content}
        if msg.tool_calls:
            assistant_entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
        messages.append(assistant_entry)

        if response.choices[0].finish_reason != "tool_calls":
            break

        for tc in msg.tool_calls:
            inputs = json.loads(tc.function.arguments)
            result = _execute_tool(tc.function.name, inputs)

            # Track document_id
            if tc.function.name == "create_report_draft" and "document_id" in result:
                _session_docs[session_id] = result["document_id"]

            # Track HWPX download URL
            if tc.function.name == "render_hwpx" and "download_url" in result:
                hwpx_url = result["download_url"]

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

    # Extract text reply
    reply_text = msg.content or ""

    # Build document snapshot (blocks 형식으로 변환해야 render_html이 정상 렌더링)
    document_id = _session_docs.get(session_id)
    document_json: Optional[dict] = None
    if document_id:
        try:
            doc = store.get(document_id)
            document_json = _doc_to_blocks_json(doc)
        except Exception:
            pass

    return {
        "reply": reply_text,
        "session_id": session_id,
        "document_id": document_id,
        "document_json": document_json,
        "hwpx_url": hwpx_url,
    }


def reset_session(session_id: str) -> dict:
    _sessions.pop(session_id, None)
    _session_docs.pop(session_id, None)
    return {"status": "reset", "session_id": session_id}
