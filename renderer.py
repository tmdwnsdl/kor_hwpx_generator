from html import escape


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
      font-family: 'HY헤드라인M', 'NanumMyeongjo', 'Nanum Myeongjo', '휴먼명조', 'Batang', serif;
      padding: 32px 16px;
    }

    /* A4 용지 - 편집여백: 위아래15mm, 좌우23mm */
    .page {
      background: #fff;
      width: 100%;
      max-width: 760px;
      margin: 0 auto;
      padding: 42px 60px 56px;
      box-shadow: 0 3px 16px rgba(0,0,0,.22);
      min-height: 600px;
    }

    /* 제목 박스 - K-water 표준서식 */
    .title-box {
      border: 1.5px solid #333;
      padding: 14px 20px 10px;
      margin-bottom: 10px;
      text-align: center;
    }
    .title-box h1 {
      font-family: 'HY헤드라인M', 'Malgun Gothic', sans-serif;
      font-size: 22px;
      font-weight: 900;
      color: #000;
      letter-spacing: 1px;
    }

    /* 취지 박스 */
    .purpose-box {
      border: 1px solid #555;
      background: #f9f9f9;
      padding: 8px 16px;
      margin-bottom: 20px;
      font-size: 14px;
      color: #333;
      line-height: 1.6;
    }

    /* 섹션 제목 - 헤드라인M 16pt */
    .section-heading {
      font-family: 'HY헤드라인M', 'Malgun Gothic', sans-serif;
      font-size: 16px;
      font-weight: 700;
      color: #000;
      margin: 20px 0 6px;
    }

    /* 본문 - TH 휴먼명조 15pt, 줄간격 150~160% */
    .body-text {
      font-family: 'NanumMyeongjo', 'Nanum Myeongjo', '휴먼명조', 'Batang', serif;
      font-size: 15px;
      color: #111;
      line-height: 1.55;
      white-space: pre-wrap;
      margin-bottom: 4px;
    }

    /* 참고내용 - 중고딕 13pt, * 표시 */
    .ref-text {
      font-family: 'Malgun Gothic', sans-serif;
      font-size: 13px;
      color: #333;
      line-height: 1.5;
      white-space: pre-wrap;
      margin: 2px 0 4px 8px;
    }

    /* 표 */
    .doc-table {
      width: 100%;
      border-collapse: collapse;
      margin: 8px 0 14px;
      font-size: 14px;
      font-family: 'NanumMyeongjo', '휴먼명조', 'Batang', serif;
    }
    .doc-table th, .doc-table td {
      border: 1px solid #444;
      padding: 6px 10px;
      vertical-align: middle;
      text-align: center;
      line-height: 1.5;
    }
    .doc-table th {
      background: #f0f0f0;
      font-weight: 700;
    }
  </style>
</head>
<body>
<div class="page">
""")

    # 제목 박스
    if title:
        parts.append(f'  <div class="title-box"><h1>{title}</h1></div>\n')
        parts.append('  <hr class="divider">\n')

    # 블록 렌더링
    for block in blocks:
        btype = block.get("type")

        if btype == "heading":
            text = escape(block.get("text", ""))
            parts.append(f'  <div class="section-heading">{text}</div>\n')

        elif btype == "paragraph":
            raw = block.get("text", "")
            if raw:
                lines = raw.split("\n")
                for line in lines:
                    escaped = escape(line)
                    if line.lstrip().startswith("*"):
                        parts.append(f'  <div class="ref-text">{escaped}</div>\n')
                    else:
                        parts.append(f'  <div class="body-text">{escaped}</div>\n')

        elif btype == "bullet_list":
            items = block.get("items", [])
            parts.append('  <ul style="margin:6px 0 6px 20px; font-size:13.5px; line-height:1.8;">\n')
            for item in items:
                parts.append(f'    <li>{escape(str(item))}</li>\n')
            parts.append('  </ul>\n')

        elif btype in ("table", "simple_table"):
            headers = block.get("headers", [])
            rows = block.get("rows", [])
            parts.append('  <table class="doc-table">\n')
            if headers:
                parts.append('    <thead><tr>\n')
                for h in headers:
                    parts.append(f'      <th>{escape(str(h))}</th>\n')
                parts.append('    </tr></thead>\n')
            parts.append('    <tbody>\n')
            for row in rows:
                parts.append('    <tr>\n')
                for cell in row:
                    parts.append(f'      <td>{escape(str(cell))}</td>\n')
                parts.append('    </tr>\n')
            parts.append('    </tbody>\n')
            parts.append('  </table>\n')

    parts.append("</div>\n</body>\n</html>")
    return "".join(parts)


if __name__ == "__main__":
    sample_doc = {
        "title": "LLM 기술 활용 방안",
        "blocks": [
            {"type": "heading", "text": "1. 추진배경"},
            {"type": "paragraph", "text": "최근 인공지능 기술의 급속한 발전으로 LLM 도입의 필요성이 대두되고 있음."},
            {"type": "heading", "text": "2. 주요내용"},
            {"type": "paragraph", "text": "LLM 기반 업무 자동화 및 보고서 작성 지원 시스템 구축을 추진함."},
            {"type": "table",
             "headers": ["기술", "활용 분야", "기대효과"],
             "rows": [["GPT-4o", "보고서 작성", "업무 효율 향상"],
                      ["Claude", "문서 분석", "정확도 개선"]]},
            {"type": "heading", "text": "3. 기대효과"},
            {"type": "paragraph", "text": "본 사업을 통해 연간 업무 시간 30% 절감 및 보고서 품질 향상이 기대됨."},
        ]
    }
    html = render_html(sample_doc)
    with open("preview_test.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("preview_test.html 생성 완료")
