from typing import Any, Dict, List


def json_to_hwpx_text(doc_json: Dict[str, Any]) -> str:
    """
    JSON 문서 구조를 HWPX 생성용 단순 텍스트로 변환한다.
    현재는 안전한 1차 버전:
    - heading / paragraph / bullet_list / table 지원
    - table은 텍스트 표 형태로 풀어서 넣음
    """
    blocks: List[Dict[str, Any]] = doc_json.get("blocks", [])
    parts: List[str] = []

    for block in blocks:
        block_type = block.get("type")

        if block_type == "heading":
            text = str(block.get("text", "")).strip()
            if text:
                parts.append(text)
                parts.append("")

        elif block_type == "paragraph":
            text = str(block.get("text", "")).strip()
            if text:
                parts.append(text)
                parts.append("")

        elif block_type == "bullet_list":
            items = block.get("items", [])
            for item in items:
                parts.append(f"• {str(item).strip()}")
            parts.append("")

        elif block_type == "table":
            headers = block.get("headers", [])
            rows = block.get("rows", [])

            if headers:
                parts.append(" | ".join(str(h).strip() for h in headers))
                parts.append("-" * 40)

            for row in rows:
                parts.append(" | ".join(str(cell).strip() for cell in row))

            parts.append("")

    return "\n".join(parts).strip()