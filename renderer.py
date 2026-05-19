import re
from html import escape


def _apply_bold(text: str) -> str:
    """**text** 마크다운 볼드를 <strong> 태그로 변환"""
    return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)


# 줄 첫 기호 → (margin-top, margin-left, is_ref)
# margin-top: HWPX 빈줄 spacer 크기에 대응 (8/5/3/1pt)
# margin-left: HWPX 스페이스 1/2/3/4칸에 대응
def _line_style(line: str) -> tuple:
    s = line.lstrip()
    if re.match(r'^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅰⅱⅲⅳⅴ]', s):
        return "8pt",  "0",    False
    if s.startswith(('□', 'ㅁ')):
        return "5pt",  "1ch",  False
    if s.startswith(('◦', '○', 'ㅇ')):
        return "3pt",  "2ch",  False
    if s.startswith('-'):
        return "1pt",  "3ch",  False
    if s.startswith(('*', '※')):
        return "1pt",  "4ch",  True
    return "5pt", "1ch", False  # 기본값 → □ 수준


def render_html(doc_json: dict) -> str:
    title = escape(doc_json.get("title", ""))
    blocks = doc_json.get("blocks", [])

    parts = []
    parts.append("""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Nanum+Myeongjo:wght@400;700&display=swap');

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background: #d0d0d0;
      padding: 32px 16px;
    }

    /* A4 용지 */
    .page {
      background: #fff;
      width: 100%;
      max-width: 760px;
      margin: 0 auto;
      padding: 42px 60px 56px;
      box-shadow: 0 3px 16px rgba(0,0,0,.22);
      min-height: 600px;
    }

    /* 제목 박스 */
    .title-box {
      border-top: 3px solid #0099FF;
      border-bottom: 3px solid #0099FF;
      background: linear-gradient(to bottom, #FFFFFF, #CCFFFF);
      padding: 14px 20px 12px;
      margin-bottom: 18px;
      text-align: center;
    }
    .title-box h1 {
      font-family: 'HY헤드라인M', 'Malgun Gothic', sans-serif;
      font-size: 22px;
      font-weight: 900;
      color: #000;
      letter-spacing: 1px;
    }

    /* 섹션 제목 — HY헤드라인M 16pt, 앞 여백 8pt */
    .section-heading {
      font-family: 'HY헤드라인M', 'Malgun Gothic', sans-serif;
      font-size: 16px;
      font-weight: 700;
      color: #000;
      margin-top: 8pt;
      margin-bottom: 0;
    }

    /* 본문 — 휴먼명조 15pt, 줄간격 160% */
    .body-line {
      font-family: 'NanumMyeongjo', 'Nanum Myeongjo', '휴먼명조', 'Batang', serif;
      font-size: 15px;
      color: #111;
      line-height: 1.6;
    }

    /* 참고내용 — 한양중고딕 13pt */
    .ref-line {
      font-family: 'Malgun Gothic', sans-serif;
      font-size: 13px;
      color: #333;
      line-height: 1.55;
    }

    /* 표 — 맑은고딕 12pt, margin-left 1칸(1ch) */
    .doc-table {
      border-collapse: collapse;
      margin-left: 1ch;
      margin-right: 0;
      width: calc(100% - 1ch);
      font-size: 12pt;
      font-family: 'Malgun Gothic', '맑은고딕', sans-serif;
      table-layout: auto;
    }
    .doc-table th, .doc-table td {
      padding: 5px 14px;
      vertical-align: middle;
      text-align: center;
      line-height: 1.5;
      white-space: nowrap;
    }
    /* 목차행 — 배경 #F2F2F2, 상단 0.3mm, 하단 이중선, 내부 세로 0.12mm */
    .doc-table th {
      background: #F2F2F2;
      font-weight: 700;
      border-top: 0.3mm solid #000;
      border-bottom: 2px double #000;
    }
    .doc-table th:not(:first-child) { border-left: 0.12mm solid #000; }
    /* 데이터행 */
    .doc-table td {
      border-top: 0.12mm solid #000;
      border-bottom: 0.12mm solid #000;
    }
    .doc-table td:not(:first-child) { border-left: 0.12mm solid #000; }
    /* 마지막 행 하단 0.3mm */
    .doc-table tr:last-child td { border-bottom: 0.3mm solid #000; }

    /* 그림표 — 윗줄: 그림 넣을 빈 칸, 아랫줄: 캡션 */
    .img-table {
      border-collapse: collapse;
      margin-left: 1ch;
      width: calc(100% - 1ch);
      font-size: 12pt;
      font-family: 'Malgun Gothic', '맑은고딕', sans-serif;
      table-layout: fixed;
    }
    .img-table td {
      border: 0.12mm solid #000;
      text-align: center;
      vertical-align: middle;
    }
    .img-table .img-cell {
      height: 120px;
      color: #bbb;
      font-size: 13px;
      background: #fafafa;
    }
    .img-table .img-cap { padding: 6px 8px; }
  </style>
</head>
<body>
<div class="page">
""")

    # 제목 박스
    if title:
        parts.append(f'  <div class="title-box"><h1>{title}</h1></div>\n')

    # 블록 렌더링
    for block in blocks:
        btype = block.get("type")

        if btype == "heading":
            text = _apply_bold(escape(block.get("text", "")))
            parts.append(f'  <div class="section-heading">{text}</div>\n')

        elif btype == "paragraph":
            raw = block.get("text", "")
            if raw:
                for line in raw.split("\n"):
                    if not line.strip():
                        continue
                    mt, ml, is_ref = _line_style(line)
                    cls = "ref-line" if is_ref else "body-line"
                    style = f'margin-top:{mt}; margin-left:{ml};'
                    rendered = _apply_bold(escape(line.lstrip()))
                    parts.append(f'  <div class="{cls}" style="{style}">{rendered}</div>\n')

        elif btype == "bullet_list":
            items = block.get("items", [])
            for item in items:
                mt, ml, is_ref = _line_style(str(item))
                cls = "ref-line" if is_ref else "body-line"
                style = f'margin-top:{mt}; margin-left:{ml};'
                parts.append(f'  <div class="{cls}" style="{style}">{_apply_bold(escape(str(item)))}</div>\n')

        elif btype in ("table", "simple_table"):
            headers = block.get("headers", [])
            rows = block.get("rows", [])
            parts.append('  <table class="doc-table" style="margin-top:5pt;">\n')
            if headers:
                parts.append('    <thead><tr>\n')
                for h in headers:
                    parts.append(f'      <th>{_apply_bold(escape(str(h)))}</th>\n')
                parts.append('    </tr></thead>\n')
            parts.append('    <tbody>\n')
            for row in rows:
                parts.append('    <tr>\n')
                for cell in row:
                    parts.append(f'      <td>{_apply_bold(escape(str(cell)))}</td>\n')
                parts.append('    </tr>\n')
            parts.append('    </tbody>\n')
            parts.append('  </table>\n')

        elif btype == "image_table":
            captions = block.get("captions", [])
            n = max(len(captions), 1)
            parts.append('  <table class="img-table" style="margin-top:5pt;">\n')
            parts.append('    <tr>\n')
            for _ in range(n):
                parts.append('      <td class="img-cell">그림</td>\n')
            parts.append('    </tr>\n    <tr>\n')
            for i in range(n):
                cap = escape(str(captions[i])) if i < len(captions) else ""
                parts.append(f'      <td class="img-cap">{cap}</td>\n')
            parts.append('    </tr>\n  </table>\n')

    parts.append("</div>\n</body>\n</html>")
    return "".join(parts)


if __name__ == "__main__":
    sample_doc = {
        "title": "공공기관 LLM 서비스 도입",
        "blocks": [
            {"type": "heading", "text": "1. 추진배경"},
            {"type": "paragraph", "text": "□ **디지털 전환** 가속화: 공공기관의 **디지털 전환** 필요성이 급증하고 있음.\n□ **효율성** 증대 필요: 인공지능 기술을 활용하여 업무 효율성을 높일 필요가 있음.\n* 관련 근거: 디지털정부법 제00조"},
            {"type": "heading", "text": "2. 현황 및 문제점"},
            {"type": "paragraph", "text": "□ **인공지능 도입 사례**: 일부 기관에서 **AI** 활용을 위한 초기 단계\n□ **기술적 한계**: LLM 서비스에 대한 기술적 이해와 인프라 부족"},
            {"type": "heading", "text": "3. 추진방향 및 계획"},
            {"type": "paragraph", "text": "□ **LLM 서비스** 구축 목표 설정: 공공서비스에 맞는 **맞춤형 LLM** 도입"},
            {"type": "table",
             "headers": ["구분", "내용", "일정"],
             "rows": [["1단계", "기반 인프라 구축", "'26. 1분기"],
                      ["2단계", "파일럿 서비스 운영", "'26. 2분기"]]},
        ]
    }
    html = render_html(sample_doc)
    with open("preview_test.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("preview_test.html 생성 완료")
