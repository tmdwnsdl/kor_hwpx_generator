import ast


def process_command(doc_json: dict, command: str) -> dict:
    command = command.strip()

    # 제목 변경: "제목을 XXX로 바꿔"
    if command.startswith("제목을 ") and command.endswith("로 바꿔"):
        new_title = command[len("제목을 "):-len("로 바꿔")].strip()
        if new_title:
            doc_json["title"] = new_title
        return doc_json

    # 2. 개요 문단 변경
    if command.startswith("개요 문단을 ") and command.endswith("로 바꿔"):
        new_text = command[len("개요 문단을 "):-len("로 바꿔")].strip()

        for idx, block in enumerate(doc_json.get("blocks", [])):
            if block.get("type") == "heading" and "개요" in block.get("text", ""):
                if idx + 1 < len(doc_json["blocks"]):
                    next_block = doc_json["blocks"][idx + 1]
                    if next_block.get("type") == "paragraph":
                        next_block["text"] = new_text
                        return doc_json

        return doc_json

    # 🔥 3. 표 행 추가
    if command.startswith("표에 ") and command.endswith(" 추가해"):
        row_text = command[len("표에 "):-len(" 추가해")].strip()

        try:
            # 문자열 → 리스트 변환
            new_row = ast.literal_eval(row_text)

            # table 찾기
            for block in doc_json.get("blocks", []):
                if block.get("type") == "table":
                    block.setdefault("rows", []).append(new_row)
                    return doc_json

        except Exception:
            return doc_json

    return doc_json