from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import uuid

from renderer import render_html
from hwpx_renderer import render_hwpx_real
from chat_service import chat as chat_service, reset_session, store, _doc_to_blocks_json

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "storage" / "hwpx"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/preview", response_class=HTMLResponse)
def preview(doc_json: dict):
    """
    JSON 문서를 받아 HTML로 변환해서 반환
    """
    return render_html(doc_json)


@app.post("/generate-hwpx")
def generate_hwpx(doc_json: dict):
    path = render_hwpx_real(doc_json)

    print("generated path =", path)
    print("generated exists =", Path(path).exists())

    return {
        "message": "HWPX 생성 완료",
        "filename": Path(path).name,
        "download_url": f"/download-hwpx/{Path(path).name}"
    }


@app.get("/download-hwpx/{filename}")
def download_hwpx(filename: str):
    file_path = OUTPUT_DIR / filename

    print("download file_path =", file_path)
    print("exists =", file_path.exists())

    if not file_path.exists():
        return {"error": "파일이 존재하지 않습니다."}

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream"
    )


# ── 수동 HWPX 다운로드 ────────────────────────────────────────────────────────────
@app.post("/render-hwpx")
def render_hwpx_manual(data: dict):
    """document_id를 받아 HWPX를 생성하고 다운로드 URL을 반환합니다."""
    document_id = data.get("document_id", "")
    if not document_id:
        raise HTTPException(status_code=400, detail="document_id가 필요합니다.")
    try:
        doc = store.get(document_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
    blocks_json = _doc_to_blocks_json(doc)
    path = render_hwpx_real(blocks_json)
    filename = Path(path).name
    return {"filename": filename, "download_url": f"/download-hwpx/{filename}"}


# ── Chat endpoints ─────────────────────────────────────────────────────────────

@app.post("/chat")
def chat(data: dict):
    """LLM과 대화하여 HWPX 보고서를 작성합니다. file_content(MD 파일 내용)를 선택적으로 포함할 수 있습니다."""
    session_id = data.get("session_id") or str(uuid.uuid4())
    message = data.get("message", "").strip()
    file_content = data.get("file_content") or None
    if not message:
        return {"error": "message가 비어 있습니다."}
    return chat_service(session_id=session_id, user_message=message, file_content=file_content)


@app.post("/chat/reset")
def chat_reset(data: dict):
    """세션을 초기화합니다."""
    session_id = data.get("session_id", "")
    return reset_session(session_id)


@app.get("/chat-ui", response_class=HTMLResponse)
def chat_ui():
    """채팅 UI 페이지를 반환합니다."""
    ui_path = Path(__file__).resolve().parent / "chat.html"
    return ui_path.read_text(encoding="utf-8")