"""
LLM 없이 HWPX 생성을 직접 테스트하는 스크립트.
python test_hwpx.py 로 실행
"""
import sys, zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hwpx_renderer import render_hwpx_real, TEMPLATE_PATH

DOC = {
    "title": "LLM을 이용한 HWPX 변환기 프로그램 개발 보고서",
    "blocks": [
        {"type": "heading", "text": "1. 추진배경", "level": 2},
        {"type": "paragraph", "text": (
            "최근 공공기관 및 기업에서 문서 자동화 수요가 급증하고 있으며, 특히 한글 문서(HWP/HWPX) 형식은 "
            "국내 행정 및 업무 환경에서 표준적으로 사용되고 있다. "
            "그러나 기존 문서 작성 방식은 수작업 의존도가 높아 시간과 비용이 과다하게 소요되는 문제가 있다. "
            "이에 따라 대규모 언어 모델(LLM)을 활용하여 자연어 대화만으로 공식 보고서를 자동 생성하는 "
            "시스템의 필요성이 대두되고 있으며, 본 프로젝트는 이러한 사회적 요구에 부응하기 위해 추진되었다."
        )},
        {"type": "heading", "text": "2. 주요내용", "level": 2},
        {"type": "paragraph", "text": (
            "본 시스템은 FastAPI 기반의 백엔드 서버와 GPT-4o 언어 모델을 연동하여 구성된다. "
            "사용자가 웹 채팅 인터페이스에서 보고서 작성 요청을 입력하면, LLM이 내용을 분석하고 "
            "적절한 도구(create_report_draft, set_section_text, render_hwpx 등)를 순차적으로 호출한다. "
            "백엔드는 JSON 형식으로 문서 구조를 관리하며, 작성 완료 후 HWPX 템플릿에 내용을 삽입하여 "
            "실제 한글 문서 파일을 생성한다. 생성된 파일은 즉시 다운로드 가능하며, "
            "작성 과정에서 실시간 HTML 미리보기를 통해 내용을 확인할 수 있다."
        )},
        {"type": "table", "headers": ["구성 요소", "기술 스택", "역할"],
         "rows": [
             ["프론트엔드", "HTML/JS (chat.html)", "채팅 UI 및 미리보기"],
             ["백엔드", "FastAPI (api.py)", "REST API 및 세션 관리"],
             ["LLM", "GPT-4o (OpenAI)", "대화 분석 및 도구 호출"],
             ["문서 저장", "JSON 파일 (storage/json)", "보고서 구조 영속화"],
             ["파일 생성", "HWPX 렌더러", "한글 문서 파일 출력"],
         ]},
        {"type": "heading", "text": "3. 기대효과", "level": 2},
        {"type": "paragraph", "text": (
            "본 프로그램 도입을 통해 보고서 초안 작성 시간을 기존 대비 70% 이상 단축할 수 있을 것으로 기대된다. "
            "담당자는 세부 내용 입력에만 집중할 수 있어 업무 집중도와 문서 품질이 동시에 향상될 것이다. "
            "또한 표준화된 문서 구조를 LLM이 자동으로 적용함으로써 부서 간 보고서 형식의 일관성을 확보할 수 있다. "
            "장기적으로는 반복적인 행정 문서 작업을 자동화하여 조직 전반의 생산성 향상에 기여할 것으로 판단된다."
        )},
    ],
}

# ── 1. 템플릿 플레이스홀더 확인 ────────────────────────────────────────────────
print("=== 1. 템플릿 플레이스홀더 확인 ===")
with zipfile.ZipFile(TEMPLATE_PATH, "r") as zf:
    raw_bytes = zf.read("Contents/section0.xml")

# 파일 인코딩 감지
for enc in ("utf-8-sig", "utf-8", "euc-kr"):
    try:
        raw_bytes.decode(enc)
        print(f"  인코딩: {enc}")
        detected_enc = enc
        break
    except Exception:
        continue

keywords = ["Title", "section1_body", "section2_body", "section3_body"]
for kw in keywords:
    found = kw.encode("utf-8") in raw_bytes
    print(f"  '{kw}' 존재: {found}")

# ── 2. HWPX 생성 ──────────────────────────────────────────────────────────────
print()
print("=== 2. HWPX 생성 ===")
try:
    output_path = render_hwpx_real(DOC)
    print(f"  경로: {output_path}")
    print(f"  크기: {Path(output_path).stat().st_size:,} bytes")

    # 생성된 파일 검사
    with zipfile.ZipFile(output_path, "r") as zf:
        result_bytes = zf.read("Contents/section0.xml")

    print()
    print("=== 3. 교체 결과 확인 ===")
    for kw in keywords:
        still_exists = kw.encode("utf-8") in result_bytes
        status = "실패 (아직 남아있음)" if still_exists else "성공"
        print(f"  '{kw}' 교체: {status}")

    # section1_body 주변 XML 컨텍스트 출력
    print()
    print("=== 4. section1_body 주변 XML (교체 전 템플릿) ===")
    idx = raw_bytes.find(b"section1_body")
    if idx >= 0:
        snippet = raw_bytes[max(0, idx-120):idx+200]
        print(snippet.decode("utf-8", errors="replace"))
    else:
        print("  찾을 수 없음")

    print()
    print("=== 5. 교체 후 해당 위치 XML ===")
    target = "최근 공공기관".encode("utf-8")
    idx2 = result_bytes.find(target)
    if idx2 >= 0:
        snippet2 = result_bytes[max(0, idx2-80):idx2+200]
        print(snippet2.decode("utf-8", errors="replace"))
    else:
        print("  교체된 텍스트를 찾을 수 없음 (교체 자체가 안된 것)")

except Exception as e:
    print(f"  오류: {e}")
    import traceback; traceback.print_exc()
