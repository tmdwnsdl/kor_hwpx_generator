from html import escape


def render_html(doc_json: dict) -> str:
    """
    JSON 문서 구조를 HTML 문자열로 변환한다.
    지원 블록:
    - heading
    - paragraph
    - bullet_list
    - table
    """

    title = escape(doc_json.get("title", ""))
    blocks = doc_json.get("blocks", [])

    html_parts = []

    # 문서 전체 wrapper
    html_parts.append("""
    <html>
    <head>
        <meta charset="utf-8">
        <title>문서 미리보기</title>
        <style>
            body {
                font-family: "Malgun Gothic", Arial, sans-serif;
                line-height: 1.6;
                max-width: 900px;
                margin: 40px auto;
                padding: 0 24px;
                color: #222;
                background: #fff;
            }
            h1, h2, h3, h4, h5, h6 {
                margin-top: 1.4em;
                margin-bottom: 0.6em;
            }
            p {
                margin: 0.8em 0;
                white-space: pre-wrap;
            }
            ul {
                margin: 0.8em 0 0.8em 1.2em;
            }
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 1em 0;
            }
            th, td {
                border: 1px solid #999;
                padding: 8px 10px;
                text-align: left;
                vertical-align: top;
            }
            th {
                background: #f2f2f2;
            }
            .doc-title {
                border-bottom: 2px solid #333;
                padding-bottom: 10px;
                margin-bottom: 24px;
            }
        </style>
    </head>
    <body>
    """)

    # 문서 제목
    if title:
        html_parts.append(f'<h1 class="doc-title">{title}</h1>')

    # 블록 렌더링
    for block in blocks:
        block_type = block.get("type")

        if block_type == "heading":
            level = block.get("level", 1)

            # h1 ~ h6 범위 제한
            if not isinstance(level, int) or level < 1:
                level = 1
            if level > 6:
                level = 6

            text = escape(block.get("text", ""))
            html_parts.append(f"<h{level}>{text}</h{level}>")

        elif block_type == "paragraph":
            text = escape(block.get("text", ""))
            html_parts.append(f"<p>{text}</p>")

        elif block_type == "bullet_list":
            items = block.get("items", [])
            html_parts.append("<ul>")
            for item in items:
                html_parts.append(f"<li>{escape(str(item))}</li>")
            html_parts.append("</ul>")

        elif block_type == "table":
            headers = block.get("headers", [])
            rows = block.get("rows", [])

            html_parts.append("<table>")

            # 헤더
            if headers:
                html_parts.append("<thead><tr>")
                for header in headers:
                    html_parts.append(f"<th>{escape(str(header))}</th>")
                html_parts.append("</tr></thead>")

            # 바디
            html_parts.append("<tbody>")
            for row in rows:
                html_parts.append("<tr>")
                for cell in row:
                    html_parts.append(f"<td>{escape(str(cell))}</td>")
                html_parts.append("</tr>")
            html_parts.append("</tbody>")

            html_parts.append("</table>")

        else:
            # 아직 지원하지 않는 타입은 무시
            continue

    html_parts.append("""
    </body>
    </html>
    """)

    return "".join(html_parts)


if __name__ == "__main__":
    sample_doc = {
        "title": "문서 자동화 보고서",
        "blocks": [
            {"type": "heading", "level": 1, "text": "1. 개요"},
            {"type": "paragraph", "text": "이 보고서는 문서 자동화 방향을 검토하기 위해 작성되었다."},
            {"type": "bullet_list", "items": ["초안 자동 생성", "HTML 미리보기", "최종 HWPX 생성"]},
            {
                "type": "table",
                "headers": ["구분", "내용"],
                "rows": [
                    ["목표", "문서 작성 자동화"],
                    ["방식", "JSON 기반 렌더링"]
                ]
            }
        ]
    }

    html = render_html(sample_doc)

    with open("preview_test.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("preview_test.html 생성 완료")