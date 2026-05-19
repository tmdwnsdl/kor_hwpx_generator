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
    {"key": "background", "heading": "추진배경"},
    {"key": "content", "heading": "주요내용"},
    {"key": "expected_effect", "heading": "기대효과"},
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
        self,
        title: str,
        author: str = "",
        department: str = "",
        sections: Optional[List[Dict[str, str]]] = None,
    ) -> ReportDocument:
        document_id = f"doc_{uuid4().hex[:8]}"
        section_defs = sections if sections else DEFAULT_SECTIONS
        doc = ReportDocument(
            document_id=document_id,
            title=title,
            meta={
                "author": author,
                "department": department,
                "date": datetime.now().strftime("%Y-%m-%d"),
            },
            sections=[
                Section(key=s["key"], heading=s["heading"])
                for s in section_defs
            ],
        )
        self.save(doc)
        return doc


store = DocumentStore()


# ── HWPX conversion ────────────────────────────────────────────────────────────
def _doc_to_blocks_json(doc: ReportDocument) -> dict:
    """DocumentStore 형식 → hwpx_renderer가 요구하는 blocks 형식 변환"""
    blocks: List[dict] = []
    for i, section in enumerate(doc.sections, 1):
        heading_text = f"{i}. {section.heading}"
        blocks.append({"type": "heading", "text": heading_text, "level": 2})
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
            elif btype == "image_table":
                blocks.append(
                    {
                        "type": "image_table",
                        "captions": block.get("captions", []),
                    }
                )
    return {"title": doc.title, "blocks": blocks}


# ── Tool definitions ───────────────────────────────────────────────────────────
TOOLS: List[dict] = [
    {
        "type": "function",
        "function": {
            "name": "create_report_draft",
            "description": (
                "새 문서 초안을 생성합니다. "
                "반드시 사용자가 섹션 목록을 선택/확인한 이후에만 호출하세요. "
                "sections에 사용자가 선택한 섹션 구성을 정확히 지정하세요. "
                "각 섹션은 key(영문 snake_case 식별자)와 heading(한글 제목)으로 구성됩니다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "문서 제목"},
                    "author": {"type": "string", "description": "작성자 이름 (선택)"},
                    "department": {"type": "string", "description": "부서명 (선택)"},
                    "sections": {
                        "type": "array",
                        "description": (
                            "사용자가 선택한 섹션 목록. "
                            "예) [{key:'background',heading:'추진배경'},{key:'plan',heading:'추진방향 및 계획'}]"
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "key": {"type": "string"},
                                "heading": {"type": "string"},
                            },
                            "required": ["key", "heading"],
                        },
                    },
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
                        "description": "create_report_draft에서 지정한 섹션 key값",
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
                        "description": "create_report_draft에서 지정한 섹션 key값",
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
            "name": "add_image_table",
            "description": (
                "특정 섹션에 그림(사진)을 넣을 수 있는 표를 추가합니다. "
                "윗줄은 그림을 넣을 빈 칸, 아랫줄은 각 그림의 캡션입니다. "
                "captions 목록의 길이가 표의 열(그림) 개수가 됩니다. "
                "그림 파일 자체는 사용자가 한글에서 직접 삽입하므로, 빈 칸 표 구조만 생성합니다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {"type": "string"},
                    "section_key": {
                        "type": "string",
                        "description": "create_report_draft에서 지정한 섹션 key값",
                    },
                    "captions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "각 그림 칸 아래에 들어갈 캡션 목록. "
                            "목록 길이 = 표의 열 개수. "
                            "캡션이 필요 없는 칸은 빈 문자열(\"\")로 두세요. "
                            "예: ['어린이 안전일기장', '안전체험교실', '안전 골든벨']"
                        ),
                    },
                },
                "required": ["document_id", "section_key", "captions"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_table",
            "description": (
                "특정 섹션의 기존 표를 수정합니다. "
                "table_index는 해당 섹션에서 표의 순서(0부터 시작)입니다. "
                "headers 또는 rows 중 변경할 항목만 전달해도 됩니다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {"type": "string"},
                    "section_key": {
                        "type": "string",
                        "description": "create_report_draft에서 지정한 섹션 key값",
                    },
                    "table_index": {
                        "type": "integer",
                        "description": "수정할 표의 순서 (0부터 시작, 섹션 내 표 기준)",
                    },
                    "headers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "새 헤더 목록 (변경 시에만 전달)",
                    },
                    "rows": {
                        "type": "array",
                        "items": {"type": "array", "items": {"type": "string"}},
                        "description": "새 데이터 행 목록 (변경 시에만 전달)",
                    },
                },
                "required": ["document_id", "section_key", "table_index"],
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
            "description": "문서를 HWPX 파일로 변환합니다. 모든 섹션 내용이 완성되면 호출하세요.",
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
                sections=inputs.get("sections"),
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

        elif name == "add_image_table":
            doc = store.get(inputs["document_id"])
            section = next(
                (s for s in doc.sections if s.key == inputs["section_key"]), None
            )
            if section is None:
                return {"error": f"section_key '{inputs['section_key']}' not found"}
            captions = inputs["captions"]
            section.blocks.append(
                {
                    "type": "image_table",
                    "captions": captions,
                }
            )
            store.save(doc)
            return {
                "document_id": inputs["document_id"],
                "section_key": inputs["section_key"],
                "column_count": len(captions),
                "updated_at": doc.updated_at,
            }

        elif name == "update_table":
            doc = store.get(inputs["document_id"])
            section = next(
                (s for s in doc.sections if s.key == inputs["section_key"]), None
            )
            if section is None:
                return {"error": f"section_key '{inputs['section_key']}' not found"}
            # 섹션 내 표만 필터링해서 index로 찾기
            table_blocks = [b for b in section.blocks if b.get("type") == "simple_table"]
            idx = inputs["table_index"]
            if idx < 0 or idx >= len(table_blocks):
                return {"error": f"table_index {idx} out of range (표 {len(table_blocks)}개 존재)"}
            target = table_blocks[idx]
            if "headers" in inputs:
                target["headers"] = inputs["headers"]
            if "rows" in inputs:
                target["rows"] = inputs["rows"]
            store.save(doc)
            return {
                "document_id": inputs["document_id"],
                "section_key": inputs["section_key"],
                "table_index": idx,
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
SYSTEM_PROMPT = """당신은 K-water(한국수자원공사)의 공식 문서 작성을 전문으로 돕는 어시스턴트입니다.
사용자와 대화하며 K-water 표준서식에 맞는 HWPX 형식의 문서를 함께 완성합니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[작업 흐름 - 반드시 이 순서를 따를 것]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 1. 제목 확인
  - 사용자가 문서 제목을 언급하면 그대로 사용
  - 제목이 없으면 먼저 제목을 물어볼 것

STEP 2. 섹션 목록 제안 (create_report_draft 호출 전에 반드시 먼저 사용자에게 제안)
  - 문서 제목과 성격을 파악해 적합한 섹션 후보 목록을 번호로 제시
  - 반드시 아래 형식으로 출력:

    📋 **[문서 제목]** 에 들어갈 섹션을 선택해 주세요.

    1. 섹션명A
    2. 섹션명B
    3. 섹션명C
    ...

    원하시는 번호를 선택해 주세요. (예: "1, 2, 4" 또는 "전체" 또는 "순서 바꿔서 2, 1, 3")

STEP 3. 사용자 선택 확인 후 create_report_draft 호출
  - 사용자가 섹션을 선택/확인하면 선택한 섹션만으로 create_report_draft 호출
  - 사용자가 "전체" 또는 "그대로"라고 하면 제안한 전체 섹션 사용
  - 사용자가 섹션 추가/변경/순서 조정을 원하면 반영 후 진행

STEP 4. 각 섹션 내용 작성
  - 각 섹션 내용을 set_section_text로 입력
  - 표가 필요하면 add_simple_table 호출
  - 그림(사진)을 넣을 자리가 필요하면 add_image_table 호출
    (그림 파일은 사용자가 한글에서 직접 삽입하므로 빈 그림칸 + 캡션 표만 생성)
  - 사용자가 제공한 정보를 최우선으로 반영
  - 부족한 정보는 사용자에게 질문하여 보완

STEP 5. 완성 및 다운로드
  - 모든 섹션 완성 후 render_hwpx 호출
  - 다운로드 URL 안내

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[문서 유형별 섹션 후보 (참고용, 제목에 맞게 조정)]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

기획/추진 문서:
  추진배경, 현황 및 문제점, 추진방향 및 계획, 세부 추진계획, 기대효과, 향후 일정

현황/실태 문서:
  개요, 현황, 문제점 및 시사점, 향후 계획

회의록/회의결과:
  회의 개요, 참석자, 주요 논의사항, 결정사항, 향후 조치

행사/행사결과 문서:
  행사 개요, 추진경과, 행사 내용, 결과 및 성과, 향후 계획

업무/성과 보고:
  주요 추진사항, 성과 및 실적, 문제점 및 개선사항, 향후 계획

제안서:
  제안 배경, 추진방향, 세부 내용, 기대효과, 소요예산

지침/규정:
  목적, 적용 범위, 주요 내용, 시행 일정

※ 위 목록에 없는 문서 유형도 제목을 보고 적합한 섹션을 자유롭게 제안하세요.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[K-water 문서 작성 기본원칙]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

문체:
  - 개조식 문체 사용 (~하였음, ~할 예정임, ~임)
  - 핵심 키워드(명사 위주)는 볼드체(**키워드**)로 강조, 동사·한자어에는 볼드 자제
  - 본문 중 참고내용은 '*' 표시 후 기술

숫자와 일시:
  - 날짜: 년·월·일 글자 생략, 온점으로 구분 (예: 2026. 4. 13 또는 약식 '26. 4. 13)
  - 시간: 24시 기준, 콜론으로 구분 (예: 15:20)

항목 표시:
  - 짧은 문서: □, ◦, - 등 특수기호 사용  ※ ◦ = U+25E6 (WHITE BULLET, 반드시 이 문자 사용)
  - 긴 문서 (항목 구분 필요 시):
      첫째 항목: Ⅰ, Ⅱ, Ⅲ, Ⅳ
      둘째 항목: 1., 2., 3.
      셋째 항목: 1), 2), 3)
      넷째 항목: (1), (2), (3)
  - 하위 항목은 상위 항목보다 한 칸 오른쪽에 위치

내용 원칙:
  - 수치·사실 기반의 구체적 서술
  - 사용자가 제공한 정보를 최대한 반영
  - 부족한 정보는 사용자에게 질문하여 보완

분량 (사용자가 분량을 따로 지정하지 않아 GPT가 자동 작성하는 경우):
  - 글머리표 종류별 분량 규칙:
      □, * 항목 : 항상 한 줄 (공백 포함 최소 35자, 최대 40자)
      ◦, - 항목 : 한 줄(공백 포함 최소 35자, 최대 40자) 또는
                  두 줄(공백 포함 최소 70자, 최대 80자)
  - 한 줄 절반이나 두 줄 절반처럼 어중간한 길이는 피하고, 위 글자 수에 맞춰
    줄을 꽉 채워 작성할 것
  - 사용자가 분량을 직접 지정하면 그 지시를 우선함"""


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
