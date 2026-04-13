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
    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background: #e8e8e8;
      font-family: 'Malgun Gothic', 'HY헤드라인M', sans-serif;
      padding: 32px 16px;
    }

    /* A4 용지 */
    .page {
      background: #fff;
      width: 100%;
      max-width: 740px;
      margin: 0 auto;
      padding: 38px 48px 52px;
      box-shadow: 0 2px 12px rgba(0,0,0,.15);
      min-height: 500px;
    }

    /* 제목 박스 (base_new.hwpx borderFillIDRef=6 스타일) */
    .title-box {
      border-top: 3px solid #0099FF;
      border-bottom: 3px solid #0099FF;
      background: linear-gradient(to bottom, #ffffff, #CCFFFF);
      padding: 14px 20px;
      margin-bottom: 24px;
      text-align: center;
    }
    .title-box h1 {
      font-size: 20px;
      font-weight: 700;
      color: #003366;
      letter-spacing: 0.5px;
    }

    /* 구분선 (charPrIDRef=3 스타일) */
    .divider {
      border: none;
      border-top: 1px solid #aaa;
      margin-bottom: 20px;
    }

    /* 섹션 제목 (charPrIDRef=4 스타일) */
    .section-heading {
      font-size: 15px;
      font-weight: 700;
      color: #111;
      margin: 22px 0 8px;
      padding-bottom: 2px;
    }

    /* 본문 (charPrIDRef=23 스타일) */
    .body-text {
      font-size: 13.5px;
      color: #222;
      line-height: 1.8;
      white-space: pre-wrap;
      margin-bottom: 6px;
    }

    /* 표 (borderFillIDRef=7 - 일반 선) */
    .doc-table {
      width: 100%;
      border-collapse: collapse;
      margin: 10px 0 14px;
      font-size: 13px;
    }
    .doc-table th, .doc-table td {
      border: 1px solid #555;
      padding: 6px 10px;
      vertical-align: middle;
      text-align: center;
      line-height: 1.6;
    }

    /* 섹션 사이 여백 */
    .section-gap { height: 6px; }
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
            text = escape(block.get("text", ""))
            if text:
                parts.append(f'  <div class="body-text">{text}</div>\n')

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
