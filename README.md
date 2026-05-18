# kor_hwpx_generator

**LLM 기반 K-water 표준서식 HWPX 보고서 자동 생성 서비스**

자연어로 대화하면 K-water 표준서식에 맞는 한글 문서(`.hwpx`)가 완성됩니다.
정해진 양식을 일일이 맞춰 보고서를 작성하던 반복 업무를 생성형 AI로 자동화하는 것을 목표로 만든 프로젝트입니다.

---

## 주요 기능

- **대화형 보고서 작성** — 채팅으로 요청하면 LLM이 보고서 구조를 잡고 본문·표를 채워 넣습니다.
- **K-water 표준서식 적용** — 문체(개조식), 항목 부호 체계(□ ◦ - / Ⅰ Ⅱ), 표 테두리·폰트 등 표준 양식을 정확히 재현합니다.
- **실시간 HTML 미리보기** — 작성 중인 문서를 브라우저에서 바로 확인합니다.
- **HWPX 파일 다운로드** — 한글 프로그램에서 바로 열 수 있는 `.hwpx` 파일로 내려받습니다.

## 동작 방식

LLM이 잘하는 일과 코드로 보장해야 하는 일을 분리해 설계했습니다.

| 영역 | 담당 | 이유 |
|------|------|------|
| 자연어 요청 → 보고서 구조(JSON) 변환 | LLM (GPT-4o) + tool calling | 의미 해석·구성은 AI가 강점 |
| 표준 양식(서식·표·들여쓰기) 렌더링 | 자체 HWPX 렌더링 엔진 | 정확한 양식 재현은 코드로 보장 |

사용자 요청은 LLM 에이전트 루프에서 `create_report_draft`, `set_section_text`, `add_simple_table` 등의 도구 호출로 처리되어 내부 문서 구조로 누적되고, HWPX 렌더링 엔진이 이를 표준서식 `.hwpx` 파일로 변환합니다. 보고서 작성 규칙은 시스템 프롬프트로 정형화해 AI가 매번 일관된 결과를 내도록 했습니다.

## 기술 스택

- **Backend** — Python, FastAPI, Uvicorn
- **AI** — OpenAI GPT-4o (agentic loop + tool calling)
- **문서 생성** — 자체 개발 HWPX 렌더링 엔진 (HWPX = ZIP + XML 구조를 직접 조립)
- **Frontend** — 단일 HTML 페이지 (채팅 + 미리보기 분할 UI)

## 프로젝트 구조

```
api.py              FastAPI 서버 — 엔드포인트 정의 및 모듈 연결
chat_service.py     LLM 에이전트 루프, 도구 정의, 문서 데이터 관리
hwpx_renderer.py    HWPX(.hwpx) 파일 생성 엔진
renderer.py         HTML 미리보기 생성
chat.html           채팅 + 실시간 미리보기 UI
templates/          K-water 표준서식 HWPX 템플릿
```

## 실행 방법

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 환경변수 설정 (.env 파일 생성)
echo OPENAI_API_KEY=your-api-key > .env

# 3. 서버 실행
uvicorn api:app --reload --port 8000
```

실행 후 브라우저에서 `http://localhost:8000/chat-ui` 접속.

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `GET`  | `/chat-ui` | 채팅 UI 페이지 |
| `POST` | `/chat` | LLM과 대화하여 보고서 작성 |
| `POST` | `/chat/reset` | 세션 초기화 |
| `POST` | `/preview` | 문서 JSON → HTML 미리보기 |
| `POST` | `/render-hwpx` | `document_id`로 HWPX 생성 |
| `GET`  | `/download-hwpx/{filename}` | 생성된 HWPX 다운로드 |
