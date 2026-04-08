import re
import shutil
import uuid
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "templates" / "base_new.hwpx"
OUTPUT_DIR = BASE_DIR / "storage" / "hwpx"

_TABLE_WIDTH = 47620
_CELL_HEIGHT = 1800


# ── 표 XML 생성 ────────────────────────────────────────────────────────────────
def _build_table_xml(headers: list, rows: list, table_id: int) -> str:
    col_count = max(len(headers), 1)
    row_count = len(rows) + 1
    cell_w = _TABLE_WIDTH // col_count
    last_w = _TABLE_WIDTH - cell_w * (col_count - 1)

    def cell_width(col_idx: int) -> int:
        return last_w if col_idx == col_count - 1 else cell_w

    tbl = (
        f'<hp:p id="0" paraPrIDRef="1" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="23">'
        f'<hp:tbl id="{table_id}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" '
        f'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="1" '
        f'rowCnt="{row_count}" colCnt="{col_count}" cellSpacing="0" borderFillIDRef="7" noAdjust="0">'
        f'<hp:sz width="{_TABLE_WIDTH}" widthRelTo="ABSOLUTE" '
        f'height="{_CELL_HEIGHT * row_count}" heightRelTo="ABSOLUTE" protect="0"/>'
        f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" '
        f'holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" '
        f'horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
        f'<hp:outMargin left="285" right="285" top="285" bottom="285"/>'
        f'<hp:inMargin left="565" right="565" top="0" bottom="0"/>'
    )

    for ci, h in enumerate(headers):
        tbl += (
            f'<hp:tr><hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" dirty="0" borderFillIDRef="7">'
            f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" '
            f'linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
            f'<hp:p id="0" paraPrIDRef="2" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="23"><hp:t>{xml_escape(str(h))}</hp:t></hp:run>'
            f'<hp:linesegarray/></hp:p></hp:subList>'
            f'<hp:cellAddr colAddr="{ci}" rowAddr="0"/>'
            f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
            f'<hp:cellSz width="{cell_width(ci)}" height="{_CELL_HEIGHT}"/>'
            f'<hp:cellMargin left="140" right="140" top="140" bottom="140"/></hp:tc></hp:tr>'
        ) if ci == 0 else (
            tbl + (
                f'<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" dirty="0" borderFillIDRef="7">'
                f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" '
                f'linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
                f'<hp:p id="0" paraPrIDRef="2" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
                f'<hp:run charPrIDRef="23"><hp:t>{xml_escape(str(h))}</hp:t></hp:run>'
                f'<hp:linesegarray/></hp:p></hp:subList>'
                f'<hp:cellAddr colAddr="{ci}" rowAddr="0"/>'
                f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
                f'<hp:cellSz width="{cell_width(ci)}" height="{_CELL_HEIGHT}"/>'
                f'<hp:cellMargin left="140" right="140" top="140" bottom="140"/></hp:tc>'
            )
        )

    # 헤더 행 재작성 (위 로직이 복잡하므로 단순화)
    tbl = (
        f'<hp:p id="0" paraPrIDRef="1" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="23">'
        f'<hp:tbl id="{table_id}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" '
        f'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="1" '
        f'rowCnt="{row_count}" colCnt="{col_count}" cellSpacing="0" borderFillIDRef="7" noAdjust="0">'
        f'<hp:sz width="{_TABLE_WIDTH}" widthRelTo="ABSOLUTE" '
        f'height="{_CELL_HEIGHT * row_count}" heightRelTo="ABSOLUTE" protect="0"/>'
        f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" '
        f'holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" '
        f'horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
        f'<hp:outMargin left="285" right="285" top="285" bottom="285"/>'
        f'<hp:inMargin left="565" right="565" top="0" bottom="0"/>'
    )

    # 헤더 행
    tbl += '<hp:tr>'
    for ci, h in enumerate(headers):
        tbl += (
            f'<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" dirty="0" borderFillIDRef="7">'
            f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" '
            f'linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
            f'<hp:p id="0" paraPrIDRef="2" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="23"><hp:t>{xml_escape(str(h))}</hp:t></hp:run>'
            f'<hp:linesegarray/></hp:p></hp:subList>'
            f'<hp:cellAddr colAddr="{ci}" rowAddr="0"/>'
            f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
            f'<hp:cellSz width="{cell_width(ci)}" height="{_CELL_HEIGHT}"/>'
            f'<hp:cellMargin left="140" right="140" top="140" bottom="140"/></hp:tc>'
        )
    tbl += '</hp:tr>'

    # 데이터 행
    for ri, row in enumerate(rows):
        tbl += '<hp:tr>'
        for ci in range(col_count):
            cell_text = str(row[ci]) if ci < len(row) else ""
            tbl += (
                f'<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" dirty="0" borderFillIDRef="7">'
                f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" '
                f'linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
                f'<hp:p id="0" paraPrIDRef="2" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
                f'<hp:run charPrIDRef="23"><hp:t>{xml_escape(cell_text)}</hp:t></hp:run>'
                f'<hp:linesegarray/></hp:p></hp:subList>'
                f'<hp:cellAddr colAddr="{ci}" rowAddr="{ri + 1}"/>'
                f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
                f'<hp:cellSz width="{cell_width(ci)}" height="{_CELL_HEIGHT}"/>'
                f'<hp:cellMargin left="140" right="140" top="140" bottom="140"/></hp:tc>'
            )
        tbl += '</hp:tr>'

    tbl += '</hp:tbl><hp:t/></hp:run><hp:linesegarray/></hp:p>'
    return tbl


# ── 섹션 XML 생성 ──────────────────────────────────────────────────────────────
def _build_section_xml(title: str, body_parts: list, tables: list, tbl_counter: list) -> str:
    """섹션 제목 + 본문 단락들 + 표들 XML 생성"""
    result = ""

    # 섹션 제목 단락
    result += (
        f'<hp:p id="0" paraPrIDRef="1" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="4"><hp:t>{xml_escape(title)}</hp:t></hp:run>'
        f'<hp:linesegarray/></hp:p>'
    )

    # 본문 단락들
    for body_text in body_parts:
        if body_text.strip():
            result += (
                f'<hp:p id="0" paraPrIDRef="1" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
                f'<hp:run charPrIDRef="23"><hp:t>{xml_escape(body_text)}</hp:t></hp:run>'
                f'<hp:linesegarray/></hp:p>'
            )

    # 표들
    for tbl in tables:
        tbl_counter[0] += 1
        result += _build_table_xml(tbl.get("headers", []), tbl.get("rows", []), tbl_counter[0])

    # 섹션 간 빈 줄
    result += (
        '<hp:p id="0" paraPrIDRef="1" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
        '<hp:run charPrIDRef="1"/><hp:linesegarray/></hp:p>'
    )

    return result


# ── blocks → 섹션 목록 추출 ────────────────────────────────────────────────────
def _extract_sections_from_blocks(doc_json: dict) -> dict:
    title = str(doc_json.get("title", "제목없음")).strip() or "제목없음"
    blocks = doc_json.get("blocks", [])

    sections: list = []
    current: dict | None = None

    for block in blocks:
        btype = block.get("type")

        if btype == "heading":
            current = {
                "title": block.get("text", "").strip(),
                "body_parts": [],
                "tables": [],
            }
            sections.append(current)

        elif btype == "paragraph" and current is not None:
            t = block.get("text", "").strip()
            if t:
                current["body_parts"].append(t)

        elif btype == "bullet_list" and current is not None:
            items = [f"• {str(i).strip()}" for i in block.get("items", []) if str(i).strip()]
            if items:
                current["body_parts"].append("\n".join(items))

        elif btype in ("table", "simple_table") and current is not None:
            current["tables"].append(block)

    return {"title": title, "sections": sections}


# ── HWPX 파일 생성 ─────────────────────────────────────────────────────────────
def render_hwpx_real(doc_json: dict) -> str:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"템플릿 파일이 없습니다: {TEMPLATE_PATH}")

    fields = _extract_sections_from_blocks(doc_json)
    work_dir = BASE_DIR / f"temp_{uuid.uuid4().hex}"
    tbl_counter = [2000]

    try:
        work_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(TEMPLATE_PATH, "r") as zf:
            zf.extractall(work_dir)

        section_path = work_dir / "Contents" / "section0.xml"
        xml_bytes = section_path.read_bytes()

        # 1. 제목 치환
        xml_bytes = xml_bytes.replace(
            b">Title<",
            f">{xml_escape(fields['title'])}<".encode("utf-8"),
        )

        # 2. linesegarray 비우기 (글자 겹침 방지)
        xml_bytes = re.sub(
            rb"<hp:linesegarray>.*?</hp:linesegarray>",
            b"<hp:linesegarray/>",
            xml_bytes,
            flags=re.DOTALL,
        )

        # 3. 섹션 XML 동적 생성
        body_xml = b""
        for sec in fields["sections"]:
            body_xml += _build_section_xml(
                sec["title"], sec["body_parts"], sec["tables"], tbl_counter
            ).encode("utf-8")

        # 4. __BODY_CONTENT__ 단락 전체를 생성된 섹션 XML로 교체
        match = re.search(
            rb"<hp:p [^>]*>.*?__BODY_CONTENT__.*?</hp:p>",
            xml_bytes,
            re.DOTALL,
        )
        if match:
            xml_bytes = xml_bytes[: match.start()] + body_xml + xml_bytes[match.end() :]

        section_path.write_bytes(xml_bytes)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / f"report_{uuid.uuid4().hex}.hwpx"

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in work_dir.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(work_dir))

        return str(output_path)

    finally:
        if work_dir.exists():
            shutil.rmtree(work_dir)
