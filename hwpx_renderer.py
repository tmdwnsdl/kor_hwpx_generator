import re
import shutil
import uuid
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "templates" / "base.hwpx"
OUTPUT_DIR = BASE_DIR / "storage" / "hwpx"

# 표 전체 너비 (템플릿 기준, HWP 단위)
_TABLE_WIDTH = 47620
# 기본 셀 높이
_CELL_HEIGHT = 1800


# ── 표 XML 생성 ────────────────────────────────────────────────────────────────
def _build_table_xml(headers: list, rows: list, table_id: int) -> str:
    """HWPX 표 XML 문자열을 생성한다."""
    col_count = max(len(headers), 1)
    row_count = len(rows) + 1          # 헤더 포함
    cell_w = _TABLE_WIDTH // col_count
    # 마지막 열은 반올림 오차 보정
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


# ── JSON → 섹션별 텍스트 + 표 추출 ────────────────────────────────────────────
def _extract_sections_from_json(doc_json: dict) -> dict:
    title = str(doc_json.get("title", "제목없음")).strip() or "제목없음"
    blocks = doc_json.get("blocks", [])

    result: dict = {
        "title": title,
        "background": [],        # 텍스트 파트 리스트
        "background_tables": [],  # {"headers": [...], "rows": [...]} 리스트
        "content": [],
        "content_tables": [],
        "expected_effect": [],
        "expected_effect_tables": [],
    }

    current = None
    for block in blocks:
        btype = block.get("type")

        if btype == "heading":
            t = str(block.get("text", "")).strip()
            if "추진배경" in t or "개요" in t:
                current = "background"
            elif "주요내용" in t or "주요 내용" in t:
                current = "content"
            elif "기대효과" in t or "기대 효과" in t:
                current = "expected_effect"
            else:
                current = None

        elif btype == "paragraph" and current:
            t = str(block.get("text", "")).strip()
            if t:
                result[current].append(t)

        elif btype == "bullet_list" and current:
            items = [f"• {str(i).strip()}" for i in block.get("items", []) if str(i).strip()]
            if items:
                result[current].append("\n".join(items))

        elif btype in ("table", "simple_table") and current:
            headers = block.get("headers", [])
            rows = block.get("rows", [])
            if headers or rows:
                result[f"{current}_tables"].append({"headers": headers, "rows": rows})

    # 텍스트 파트를 문자열로 합치기
    for key in ("background", "content", "expected_effect"):
        result[key] = "\n".join(result[key])

    return result


# ── HWPX 파일 생성 ─────────────────────────────────────────────────────────────
def render_hwpx_real(doc_json: dict) -> str:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"템플릿 파일이 없습니다: {TEMPLATE_PATH}")

    fields = _extract_sections_from_json(doc_json)
    work_dir = BASE_DIR / f"temp_{uuid.uuid4().hex}"
    _tbl_id = [2000]  # 표 id 카운터

    def next_id() -> int:
        _tbl_id[0] += 1
        return _tbl_id[0]

    try:
        work_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(TEMPLATE_PATH, "r") as zf:
            zf.extractall(work_dir)

        section_path = work_dir / "Contents" / "section0.xml"
        if not section_path.exists():
            raise FileNotFoundError(f"section0.xml이 없습니다: {section_path}")

        xml_bytes = section_path.read_bytes()

        # ── 1. 제목/섹션 타이틀 치환 ──────────────────────────────────────────
        for placeholder, value in {
            "Title": fields["title"],
            "1. section1_title": "1. 추진배경",
            "2. section2_title": "2. 주요내용",
            "3. section3_title": "3. 기대효과",
        }.items():
            xml_bytes = xml_bytes.replace(
                f">{placeholder}<".encode(),
                f">{xml_escape(value)}<".encode(),
            )

        # ── 2. linesegarray 비우기 (글자 겹침 방지) ────────────────────────────
        xml_bytes = re.sub(
            rb"<hp:linesegarray>.*?</hp:linesegarray>",
            b"<hp:linesegarray/>",
            xml_bytes,
            flags=re.DOTALL,
        )

        # ── 3. 섹션 본문 치환 + 표 삽입 ───────────────────────────────────────
        # linesegarray를 비운 뒤 패턴이 단순해짐:
        # <hp:t>PLACEHOLDER</hp:t></hp:run><hp:linesegarray/></hp:p>
        for sec_key, placeholder in (
            ("background",      "section1_body"),
            ("content",         "section2_body"),
            ("expected_effect", "section3_body"),
        ):
            body_text = xml_escape(fields[sec_key])
            tables_xml = "".join(
                _build_table_xml(t["headers"], t["rows"], next_id())
                for t in fields[f"{sec_key}_tables"]
            )

            old = f"<hp:t>{placeholder}</hp:t></hp:run><hp:linesegarray/></hp:p>".encode()
            new = (
                f"<hp:t>{body_text}</hp:t></hp:run><hp:linesegarray/></hp:p>"
                + tables_xml
            ).encode()

            xml_bytes = xml_bytes.replace(old, new)

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
