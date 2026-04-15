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
    return {"title": doc.title, "blocks": blocks}


# ── Tool definitions ───────────────────────────────────────────────────────────
TOOLS: List[dict] = [
    {
        "type": "function",
        "function": {
            "name": "create_report_draft",
            "description": (
                "새 보고서 초안을 생성합니다. 보고서 작성을 시작할 때 가장 먼저 호출하세요. "
                "sections에 보고서 유형에 맞는 섹션 구성을 지정하세요. "
                "각 섹션은 key(영문 식별자)와 heading(한글 제목)으로 구성됩니다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "보고서 제목"},
                    "author": {"type": "string", "description": "작성자 이름 (선택)"},
                    "department": {"type": "string", "description": "부서명 (선택)"},
                    "sections": {
                        "type": "array",
                        "description": (
                            "섹션 목록. 보고서 유형에 맞게 구성. "
                            "예) 기획보고서: [{key:'background',heading:'추진배경'},{key:'issue',heading:'현황 및 문제점'},{key:'plan',heading:'추진방안'},{key:'schedule',heading:'향후계획'}] "
                            "예) 회의계획서: [{key:'overview',heading:'회의개요'},{key:'agenda',heading:'안건'},{key:'schedule',heading:'시간계획'}]"
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
SYSTEM_PROMPT = """당신은 K-water(한국수자원공사)의 공식 보고서 작성을 전문으로 돕는 어시스턴트입니다.
사용자와 대화하며 K-water 보고서 표준서식에 맞는 HWPX 형식의 보고서를 함께 완성합니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[보고서 유형별 섹션 구성 - 반드시 아래 구조를 사용할 것]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 기획 보고서
   sections: [
     {key: "background", heading: "추진배경"},
     {key: "current_status", heading: "현황 및 문제점"},
     {key: "plan", heading: "추진방향 및 계획"},
     {key: "detail_plan", heading: "세부 추진계획"},
     {key: "expected_effect", heading: "기대효과"},
     {key: "schedule", heading: "향후 일정"}
   ]

2. 현황·상황·실태 보고서
   sections: [
     {key: "overview", heading: "개요"},
     {key: "current_status", heading: "현황"},
     {key: "analysis", heading: "문제점 및 시사점"},
     {key: "future_plan", heading: "향후 계획"}
   ]

3. 회의 보고서
   sections: [
     {key: "meeting_overview", heading: "회의 개요"},
     {key: "agenda", heading: "주요 논의사항"},
     {key: "decisions", heading: "결정사항"},
     {key: "action_items", heading: "향후 조치"}
   ]

4. 행사 보고서
   sections: [
     {key: "event_overview", heading: "행사 개요"},
     {key: "progress", heading: "추진경과"},
     {key: "event_content", heading: "행사 내용"},
     {key: "result", heading: "결과 및 성과"},
     {key: "future_plan", heading: "향후 계획"}
   ]

보고서 유형이 불명확할 경우 사용자에게 확인 후 진행하세요.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[K-water 보고서 작성 기본원칙]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

문체:
  - 개조식 문체 사용 (~하였음, ~할 예정임, ~임)
  - 핵심 키워드(명사 위주)는 볼드체로 강조, 동사·한자어에는 볼드 자제
  - 본문 중 참고내용은 '*' 표시 후 기술

숫자와 일시:
  - 날짜: 년·월·일 글자 생략, 온점으로 구분 (예: 2026. 4. 13 또는 약식 '26. 4. 13)
  - 시간: 24시 기준, 콜론으로 구분 (예: 15:20)

항목 표시:
  - 짧은 보고서: □, ○, - 등 특수기호 사용
  - 긴 보고서 (항목 구분 필요 시):
      첫째 항목: Ⅰ, Ⅱ, Ⅲ, Ⅳ
      둘째 항목: 1., 2., 3.
      셋째 항목: 1), 2), 3)
      넷째 항목: (1), (2), (3)
      다섯째 항목: ①, ②, ③
  - 하위 항목은 상위 항목보다 한 칸 오른쪽에 위치

내용 원칙:
  - 수치·사실 기반의 구체적 서술
  - 사용자가 제공한 정보를 최대한 반영
  - 부족한 정보는 사용자에게 질문하여 보완

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[작업 흐름]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. 보고서 유형 파악 (불명확하면 사용자에게 확인)
  2. 해당 유형의 섹션 구조로 create_report_draft 호출
  3. 각 섹션 내용을 set_section_text로 입력
  4. 표가 필요하면 add_simple_table 호출
  5. 내용 완성 후 render_hwpx 호출
  6. 생성 완료 후 다운로드 안내

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[MD 파일 첨부 시 파싱 규칙 - 반드시 준수]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
첨부 파일 내용에 마크다운 형식이 포함된 경우 다음 규칙으로 변환하라:

1. 마크다운 표(| 항목 | 내용 |) → add_simple_table 호출
   - |---|---| 구분선 행은 무시
   - 첫 번째 행이 헤더(headers), 나머지가 rows
   - 절대로 표를 set_section_text 텍스트로 넣지 말 것

2. ### 소제목 → 해당 섹션의 heading 텍스트 또는 새 섹션
   - 한 섹션 안에 소제목이 여러 개면 set_section_text로 소제목만 먼저 입력 후 표 추가

3. > 인용문(근거, 대상 등) → set_section_text의 본문 앞에 포함

4. - ☐ 체크박스 목록 → set_section_text 텍스트로 줄바꿈 포함해서 그대로 입력
   예: "☐ 항목1\n☐ 항목2\n☐ 항목3"

5. ※ 참고사항 → 해당 섹션의 마지막 set_section_text에 포함

6. 섹션 구성: MD의 ## 대제목을 섹션으로 구성
   예) [양식 1] → section key: "form1", [양식 2] → "form2", [별첨] → "appendix"

7. 절대 금지: 마크다운 문법(|, ---, ###, >) 을 그대로 텍스트로 출력하지 말 것"""


# ── Session management ─────────────────────────────────────────────────────────
_sessions: Dict[str, List[dict]] = {}
_session_docs: Dict[str, Optional[str]] = {}


def chat(session_id: str, user_message: str, file_content: Optional[str] = None) -> dict:
    """
    사용자 메시지를 처리하고 Claude 응답을 반환합니다.
    file_content가 있으면 MD 파일 내용을 컨텍스트로 함께 전달합니다.

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

    # MD 파일 첨부 시 파일 내용을 컨텍스트로 삽입
    if file_content:
        full_message = (
            f"[첨부 파일 내용 - 아래 내용을 참고하여 작업해주세요]\n\n"
            f"{file_content}\n\n"
            f"---\n\n"
            f"{user_message}"
        )
    else:
        full_message = user_message

    messages.append({"role": "user", "content": full_message})

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
