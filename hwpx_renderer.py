import re
import shutil
import uuid
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

# charPr IDs (base_new.hwpx 기준)
_CHAR_HEADING    = "10"   # HY헤드라인M 16pt
_CHAR_BODY       = "11"   # 휴먼명조 15pt
_CHAR_BOLD       = "14"   # 휴먼명조 15pt bold
_CHAR_REF        = "13"   # 한양중고딕 13pt (참고내용 *)
_CHAR_TABLE_BODY = "15"   # 맑은고딕 12pt (표 본문)
_CHAR_TABLE_BOLD = "16"   # 맑은고딕 12pt bold (표 목차행, <hh:bold/> 태그 방식)

# 빈줄 간격용 charPr IDs (줄간격 조정 — 각 단락 앞 빈줄의 폰트 크기)
_CHAR_SP_8PT = "17"   # 8pt: Ⅰ. 수준 앞
_CHAR_SP_5PT = "18"   # 5pt: □ 수준 앞
_CHAR_SP_3PT = "19"   # 3pt: ○ 수준 앞
_CHAR_SP_1PT = "20"   # 1pt: -, * 수준 앞

# paraPr IDs
_PARA_ROMAN  = "23"   # 모든 본문 단락 공통 (left=0) — 들여쓰기는 전각공백으로 처리
_PARA_SQUARE = "24"   # 표 단락용 (left=2000, 1칸) — 텍스트 단락에는 미사용

# 전각공백(　, U+3000) 기반 들여쓰기 — 수준별 앞에 붙이는 개수
_INDENT = {
    "roman":  0,   # Ⅰ. 수준: 공백 없음
    "square": 1,   # □  수준: 　×1
    "circle": 2,   # ○  수준: 　×2
    "dash":   3,   # -   수준: 　×3
    "star":   4,   # *   수준: 　×4
}
_IDEOGRAPHIC_SPACE = "　"  # 전각공백

# borderFill IDs (표 전용) — 행 유형 × 열 위치 조합
# 비마지막열: L=NONE, R=0.12mm SOLID (내부 세로선)
# 마지막열:   L=0.12mm SOLID, R=NONE (외곽 우측 없음)
_BF_TABLE_FRAME    = "5"   # 테이블 외곽 프레임 (전체 NONE, 기존 템플릿 id=5)
# 목차행 (다중행 테이블): B=DOUBLE_SLIM 0.7mm
_BF_HDR_NL         = "6"   # 목차행, 비마지막열: L=NONE R=0.12 T=0.3 B=DS fill
_BF_HDR_L          = "7"   # 목차행, 마지막열:   L=0.12 R=NONE T=0.3 B=DS fill
# 목차행 바로 아래 첫번째 데이터행: T=DOUBLE_SLIM (헤더와 맞닿는 쪽)
_BF_FIRST_NL       = "8"   # 1st-data, 비마지막열: L=NONE R=0.12 T=DS B=0.12
_BF_FIRST_L        = "9"   # 1st-data, 마지막열:   L=0.12 R=NONE T=DS B=0.12
# 중간 데이터행 (2번째 ~ 끝에서 두번째)
_BF_MID_NL         = "10"  # mid, 비마지막열: T/B=0.12
_BF_MID_L          = "11"  # mid, 마지막열:   T/B=0.12
# 마지막 데이터행 (2개 이상 데이터행일 때)
_BF_LAST_NL        = "12"  # last, 비마지막열: T=0.12 B=0.3
_BF_LAST_L         = "13"  # last, 마지막열:   T=0.12 B=0.3
# 데이터행이 1개뿐 (첫번째 = 마지막): T=DS B=0.3
_BF_ONLY_NL        = "14"  # only-data, 비마지막열: T=DS B=0.3
_BF_ONLY_L         = "15"  # only-data, 마지막열:   T=DS B=0.3
# 목차행만 있는 단일행 테이블: B=0.3mm (이중선 없음)
_BF_HDR_ONLY_NL    = "16"  # HDR-only, 비마지막열: T=0.3 B=0.3 fill
_BF_HDR_ONLY_L     = "17"  # HDR-only, 마지막열:   T=0.3 B=0.3 fill


def _detect_level(line: str) -> tuple:
    """줄 첫 기호로 단락 수준 감지 → (indent_count, spacer_charPr, base_charPr)
    indent_count: 텍스트 앞에 붙일 전각공백(　) 개수
    """
    s = line.lstrip()
    if re.match(r'^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅰⅱⅲⅳⅴ]', s):
        return _INDENT["roman"],  _CHAR_SP_8PT, _CHAR_HEADING
    if s.startswith(('□', 'ㅁ')):
        return _INDENT["square"], _CHAR_SP_5PT, _CHAR_BODY
    if s.startswith(('○', '◦', 'ㅇ')):
        return _INDENT["circle"], _CHAR_SP_3PT, _CHAR_BODY
    if s.startswith('-'):
        return _INDENT["dash"],   _CHAR_SP_1PT, _CHAR_BODY
    if s.startswith(('*', '※')):
        return _INDENT["star"],   _CHAR_SP_1PT, _CHAR_REF
    return _INDENT["square"], _CHAR_SP_5PT, _CHAR_BODY   # 기본값 → □ 수준


def _spacer(char_pr: str) -> str:
    """지정 폰트 크기의 빈줄 단락 XML (단락 앞 줄간격 역할)"""
    return (
        f'<hp:p id="0" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="{char_pr}"/>'
        f'<hp:linesegarray/></hp:p>'
    )


def _runs_from_text(text: str, base_char: str = _CHAR_BODY) -> str:
    """**text** 마크다운을 bold run과 normal run으로 분리하여 HWPX run XML 생성"""
    parts = re.split(r'(\*\*.*?\*\*)', text)
    result = ""
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            inner = xml_escape(part[2:-2])
            result += f'<hp:run charPrIDRef="{_CHAR_BOLD}"><hp:t>{inner}</hp:t></hp:run>'
        elif part:
            result += f'<hp:run charPrIDRef="{base_char}"><hp:t>{xml_escape(part)}</hp:t></hp:run>'
    return result or f'<hp:run charPrIDRef="{base_char}"/>'

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "templates" / "base_new.hwpx"
OUTPUT_DIR = BASE_DIR / "storage" / "hwpx"

# 컬럼 너비(46488) - paraPr ㅁ수준 왼쪽여백(2000) - outMargin 양쪽(283×2) = 43922
# → ㅁ 수준(1칸) 들여쓰기 시작점에서 우측 여백까지 꽉 채움
_TABLE_WIDTH  = 43922
_CELL_HEIGHT  = 1800
_COL_MIN_WIDTH = 2000   # 최소 열 너비 (열이 많아도 찌그러지지 않게 최소 보장)


def _calc_col_widths(headers: list, rows: list) -> list[int]:
    """각 열의 최대 글자 수 기준으로 열 너비를 비례 배분"""
    col_count = len(headers)
    if col_count == 0:
        return []

    def char_weight(s: str) -> int:
        # 한글/한자 등 전각 문자는 2배 가중치
        return sum(2 if ord(c) > 0x3000 else 1 for c in str(s))

    max_weights = []
    for ci in range(col_count):
        weights = [char_weight(headers[ci])]
        for row in rows:
            if ci < len(row):
                weights.append(char_weight(str(row[ci])))
        max_weights.append(max(weights) + 2)  # 여백 여유

    total_weight = sum(max_weights)
    widths = [
        max(_COL_MIN_WIDTH, int(_TABLE_WIDTH * w / total_weight))
        for w in max_weights
    ]

    # 마지막 열을 조정해서 총 너비를 맞춤
    diff = _TABLE_WIDTH - sum(widths)
    widths[-1] = max(_COL_MIN_WIDTH, widths[-1] + diff)
    return widths


# ── 표 XML 생성 ────────────────────────────────────────────────────────────────
def _build_table_xml(headers: list, rows: list, table_id: int) -> str:
    col_count = max(len(headers), 1)
    row_count = len(rows) + 1   # 헤더 1행 + 데이터 행
    col_widths = _calc_col_widths(headers, rows)
    is_single_row = (len(rows) == 0)  # 헤더만 있는 경우

    def cell_width(col_idx: int) -> int:
        return col_widths[col_idx] if col_idx < len(col_widths) else _TABLE_WIDTH // col_count

    def hdr_bf(ci: int) -> str:
        """목차행 borderFill: 단일행/다중행 × 비마지막열/마지막열"""
        is_last = (ci == col_count - 1)
        if is_single_row:
            return _BF_HDR_ONLY_L if is_last else _BF_HDR_ONLY_NL
        else:
            return _BF_HDR_L if is_last else _BF_HDR_NL

    def data_bf(ri: int, ci: int) -> str:
        """데이터행 borderFill: 행 위치 × 열 위치 조합
        - 첫번째 행: T=DOUBLE_SLIM (목차행 이중선과 맞닿음)
        - 마지막 행: B=0.3mm (외곽 하단)
        - 데이터행 1개: 첫번째 & 마지막 (T=DS, B=0.3mm)
        """
        is_first_row = (ri == 0)
        is_last_row  = (ri == len(rows) - 1)
        is_last_col  = (ci == col_count - 1)
        if is_first_row and is_last_row:    # 데이터행 1개
            return _BF_ONLY_L if is_last_col else _BF_ONLY_NL
        elif is_first_row:                  # 첫번째 (다중행)
            return _BF_FIRST_L if is_last_col else _BF_FIRST_NL
        elif is_last_row:                   # 마지막
            return _BF_LAST_L if is_last_col else _BF_LAST_NL
        else:                               # 중간
            return _BF_MID_L if is_last_col else _BF_MID_NL

    # 테이블 외곽 프레임 (ㅁ 수준 들여쓰기 적용)
    tbl = (
        f'<hp:p id="0" paraPrIDRef="{_PARA_SQUARE}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="{_CHAR_TABLE_BODY}">'
        f'<hp:tbl id="{table_id}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" '
        f'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="1" '
        f'rowCnt="{row_count}" colCnt="{col_count}" cellSpacing="0" borderFillIDRef="{_BF_TABLE_FRAME}" noAdjust="0">'
        f'<hp:sz width="{_TABLE_WIDTH}" widthRelTo="ABSOLUTE" '
        f'height="{_CELL_HEIGHT * row_count}" heightRelTo="ABSOLUTE" protect="0"/>'
        f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" '
        f'holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="PARA" vertAlign="TOP" '
        f'horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
        f'<hp:outMargin left="283" right="283" top="283" bottom="283"/>'
        f'<hp:inMargin left="565" right="565" top="0" bottom="0"/>'
    )

    # 목차행 (헤더)
    tbl += '<hp:tr>'
    for ci, h in enumerate(headers):
        tbl += (
            f'<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" dirty="0" borderFillIDRef="{hdr_bf(ci)}">'
            f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" '
            f'linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
            f'<hp:p id="0" paraPrIDRef="1" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="{_CHAR_TABLE_BOLD}"><hp:t>{xml_escape(str(h))}</hp:t></hp:run>'
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
                f'<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" dirty="0" borderFillIDRef="{data_bf(ri, ci)}">'
                f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" '
                f'linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
                f'<hp:p id="0" paraPrIDRef="1" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
                f'<hp:run charPrIDRef="{_CHAR_TABLE_BODY}"><hp:t>{xml_escape(cell_text)}</hp:t></hp:run>'
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
    """섹션 제목 + 본문 단락들 + 표들 XML 생성
    줄간격: 각 단락 앞에 빈줄(8/5/3/1pt) 삽입
    들여쓰기: 전각공백(　, U+3000)을 텍스트 앞에 수준별로 붙임 (paraPr은 공통 left=0)
    """
    result = ""

    # ① 섹션 제목 (Ⅰ. 수준) — 8pt 빈줄 + 헤딩 단락 (전각공백 없음)
    result += _spacer(_CHAR_SP_8PT)
    result += (
        f'<hp:p id="0" paraPrIDRef="{_PARA_ROMAN}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="{_CHAR_HEADING}"><hp:t>{xml_escape(title)}</hp:t></hp:run>'
        f'<hp:linesegarray/></hp:p>'
    )

    # ② 본문 단락들 — 기호 감지 → 빈줄 삽입 + 전각공백 prefix + charPr
    for body_text in body_parts:
        for line in body_text.split("\n"):
            if not line.strip():
                continue
            indent_cnt, spacer_cpr, base_char = _detect_level(line)
            indented_line = _IDEOGRAPHIC_SPACE * indent_cnt + line.lstrip()
            runs = _runs_from_text(indented_line, base_char)
            result += _spacer(spacer_cpr)
            result += (
                f'<hp:p id="0" paraPrIDRef="{_PARA_ROMAN}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
                f'{runs}'
                f'<hp:linesegarray/></hp:p>'
            )

    # ③ 표들 — 5pt 빈줄 + paraPrIDRef=_PARA_SQUARE (left=2000, 표 위치 고정)
    for tbl in tables:
        tbl_counter[0] += 1
        result += _spacer(_CHAR_SP_5PT)
        result += _build_table_xml(tbl.get("headers", []), tbl.get("rows", []), tbl_counter[0])

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
        # rfind로 해당 단락의 정확한 <hp:p> 시작점을 찾아 교체 (regex DOTALL 오작동 방지)
        ph_pos = xml_bytes.find(b"__BODY_CONTENT__")
        if ph_pos >= 0:
            para_start = xml_bytes.rfind(b"<hp:p ", 0, ph_pos)
            para_end = xml_bytes.find(b"</hp:p>", ph_pos) + len(b"</hp:p>")
            xml_bytes = xml_bytes[:para_start] + body_xml + xml_bytes[para_end:]

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
