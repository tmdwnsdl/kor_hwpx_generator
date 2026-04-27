"""
base_new.hwpx 템플릿 재구성 스크립트
- borderFill IDs 6-17 복원 (표 테두리 시스템)
- charPr IDs 10-16 복원 (헤딩/본문/볼드/참고/표 폰트)
- itemCnt 정확하게 업데이트
- paraPr 23-27, charPr 17-20 은 이미 정상 → 유지
"""
import re
import shutil
import zipfile
from pathlib import Path

TEMPLATE = Path("templates/base_new.hwpx")
BACKUP   = Path("templates/base_new.hwpx.bak2")

# ── borderFill 헬퍼 ────────────────────────────────────────────────────────────
_NONE  = 'type="NONE" width="0.12 mm" color="#000000"'
_S12   = 'type="SOLID" width="0.12 mm" color="#000000"'
_S30   = 'type="SOLID" width="0.3 mm" color="#000000"'
_DS    = 'type="DOUBLE_SLIM" width="0.7 mm" color="#000000"'
_FILL_HEADER = '<hc:fillBrush><hc:winBrush faceColor="#F2F2F2" hatchColor="#999999" alpha="0"/></hc:fillBrush>'


def bf(fid: int, L: str, R: str, T: str, B: str, fill: str = "") -> str:
    return (
        f'<hh:borderFill id="{fid}" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">'
        f'<hh:slash type="NONE" Crooked="0" isCounter="0"/>'
        f'<hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
        f'<hh:leftBorder {L}/>'
        f'<hh:rightBorder {R}/>'
        f'<hh:topBorder {T}/>'
        f'<hh:bottomBorder {B}/>'
        f'{fill}'
        f'</hh:borderFill>'
    )


# ── 추가할 borderFill 6-17 ─────────────────────────────────────────────────────
NEW_BORDER_FILLS = (
    # id=6 : 목차행 비마지막열   L=NONE R=0.12 T=0.3 B=DS fill
    bf(6,  _NONE, _S12, _S30, _DS,  _FILL_HEADER),
    # id=7 : 목차행 마지막열     L=0.12 R=NONE T=0.3 B=DS fill
    bf(7,  _S12,  _NONE, _S30, _DS, _FILL_HEADER),
    # id=8 : 1st-data 비마지막열 L=NONE R=0.12 T=DS B=0.12
    bf(8,  _NONE, _S12, _DS,  _S12),
    # id=9 : 1st-data 마지막열   L=0.12 R=NONE T=DS B=0.12
    bf(9,  _S12,  _NONE, _DS, _S12),
    # id=10: mid 비마지막열      L=NONE R=0.12 T=0.12 B=0.12
    bf(10, _NONE, _S12, _S12, _S12),
    # id=11: mid 마지막열        L=0.12 R=NONE T=0.12 B=0.12
    bf(11, _S12,  _NONE, _S12, _S12),
    # id=12: last 비마지막열     L=NONE R=0.12 T=0.12 B=0.3
    bf(12, _NONE, _S12, _S12, _S30),
    # id=13: last 마지막열       L=0.12 R=NONE T=0.12 B=0.3
    bf(13, _S12,  _NONE, _S12, _S30),
    # id=14: only-data 비마지막열 L=NONE R=0.12 T=DS B=0.3
    bf(14, _NONE, _S12, _DS,  _S30),
    # id=15: only-data 마지막열   L=0.12 R=NONE T=DS B=0.3
    bf(15, _S12,  _NONE, _DS, _S30),
    # id=16: HDR-only 비마지막열  L=NONE R=0.12 T=0.3 B=0.3 fill
    bf(16, _NONE, _S12, _S30, _S30, _FILL_HEADER),
    # id=17: HDR-only 마지막열    L=0.12 R=NONE T=0.3 B=0.3 fill
    bf(17, _S12,  _NONE, _S30, _S30, _FILL_HEADER),
)

# ── charPr 헬퍼 ───────────────────────────────────────────────────────────────
def cp(cid: int, height: int, font_hangul: int, bold: bool = False) -> str:
    bold_tag = "<hh:bold/>" if bold else ""
    return (
        f'<hh:charPr id="{cid}" height="{height}" textColor="#000000" shadeColor="none" '
        f'useFontSpace="0" useKerning="0" symMark="NONE" borderFillIDRef="2">'
        f'<hh:fontRef hangul="{font_hangul}" latin="{font_hangul}" hanja="{font_hangul}" '
        f'japanese="{font_hangul}" other="{font_hangul}" symbol="{font_hangul}" user="{font_hangul}"/>'
        f'<hh:ratio hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>'
        f'<hh:spacing hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
        f'<hh:relSz hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>'
        f'<hh:offset hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
        f'{bold_tag}'
        f'</hh:charPr>'
    )

# 폰트 ID (HANGUL 폰트페이스 기준)
# id=0: 맑은고딕, id=1: 한양중고딕, id=2: 휴먼명조, id=3: HY헤드라인M

NEW_CHAR_PRS = (
    cp(10, 1600, 3),           # HY헤드라인M 16pt (헤딩)
    cp(11, 1500, 2),           # 휴먼명조 15pt (본문)
    cp(12, 1500, 2),           # 휴먼명조 15pt (예비 - 11과 동일)
    cp(13, 1300, 1),           # 한양중고딕 13pt (참고/*)
    cp(14, 1500, 2, bold=True),# 휴먼명조 15pt bold (**텍스트**)
    cp(15, 1200, 0),           # 맑은고딕 12pt (표 본문)
    cp(16, 1200, 0, bold=True),# 맑은고딕 12pt bold (표 헤더)
)


def main():
    # 백업
    shutil.copy2(TEMPLATE, BACKUP)
    print(f"백업 완료: {BACKUP}")

    # 압축 해제 → header.xml 수정 → 재압축
    import tempfile, os
    tmp_dir = Path(tempfile.mkdtemp())

    try:
        with zipfile.ZipFile(TEMPLATE, "r") as z:
            z.extractall(tmp_dir)

        hdr_path = tmp_dir / "Contents" / "header.xml"
        hdr = hdr_path.read_bytes().decode("utf-8")

        # ── 1) borderFill 6-17 삽입 ─────────────────────────────────────────
        # id=5 의 </hh:borderFill> 바로 뒤에 삽입
        last_bf_end = hdr.rfind("</hh:borderFill>",
                                hdr.find('<hh:borderFill id="5"'))
        insert_pos = last_bf_end + len("</hh:borderFill>")
        new_bf_xml = "".join(NEW_BORDER_FILLS)
        hdr = hdr[:insert_pos] + new_bf_xml + hdr[insert_pos:]
        print(f"borderFill 6-17 삽입 완료 ({len(NEW_BORDER_FILLS)}개)")

        # ── 2) borderFills itemCnt 업데이트 (5 → 17) ────────────────────────
        hdr = hdr.replace(
            '<hh:borderFills itemCnt="5">',
            '<hh:borderFills itemCnt="17">',
            1,
        )

        # ── 3) charPr 10-16 삽입 ────────────────────────────────────────────
        # 현재 charPr 중 id=9 의 </hh:charPr> 바로 뒤에 삽입
        id9_start = hdr.find('<hh:charPr id="9"')
        last_cp9_end = hdr.find("</hh:charPr>", id9_start)
        insert_pos = last_cp9_end + len("</hh:charPr>")
        new_cp_xml = "".join(NEW_CHAR_PRS)
        hdr = hdr[:insert_pos] + new_cp_xml + hdr[insert_pos:]
        print(f"charPr 10-16 삽입 완료 ({len(NEW_CHAR_PRS)}개)")

        # ── 4) charProperties itemCnt 업데이트 ──────────────────────────────
        # 현재 10 (id=0-9), 실제 요소는 14개(0-9 + 17-20), 추가 후 21개(0-20)
        old_cnt = re.search(r'<hh:charProperties itemCnt="(\d+)">', hdr)
        if old_cnt:
            actual_cnt = len(re.findall(r'<hh:charPr id="', hdr))
            hdr = hdr.replace(
                f'<hh:charProperties itemCnt="{old_cnt.group(1)}">',
                f'<hh:charProperties itemCnt="{actual_cnt}">',
                1,
            )
            print(f"charProperties itemCnt: {old_cnt.group(1)} → {actual_cnt}")

        # ── 5) paraProperties itemCnt 업데이트 ──────────────────────────────
        old_pcnt = re.search(r'<hh:paraProperties itemCnt="(\d+)">', hdr)
        if old_pcnt:
            actual_pcnt = len(re.findall(r'<hh:paraPr id="', hdr))
            hdr = hdr.replace(
                f'<hh:paraProperties itemCnt="{old_pcnt.group(1)}">',
                f'<hh:paraProperties itemCnt="{actual_pcnt}">',
                1,
            )
            print(f"paraProperties itemCnt: {old_pcnt.group(1)} → {actual_pcnt}")

        # 저장
        hdr_path.write_bytes(hdr.encode("utf-8"))

        # ── 6) 재압축 ────────────────────────────────────────────────────────
        TEMPLATE.unlink()
        with zipfile.ZipFile(TEMPLATE, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(tmp_dir.rglob("*")):
                if f.is_file():
                    z.write(f, f.relative_to(tmp_dir))
        print(f"템플릿 재압축 완료: {TEMPLATE}")

        # ── 7) 검증 ──────────────────────────────────────────────────────────
        with zipfile.ZipFile(TEMPLATE) as z:
            hdr_check = z.read("Contents/header.xml").decode("utf-8")
        bf_ids = sorted(set(re.findall(r'<hh:borderFill id="(\d+)"', hdr_check)), key=int)
        cp_ids = sorted(set(re.findall(r'<hh:charPr id="(\d+)"', hdr_check)), key=int)
        pp_ids = sorted(set(re.findall(r'<hh:paraPr id="(\d+)"', hdr_check)), key=int)
        print("\n── 검증 결과 ──")
        print(f"borderFill IDs : {bf_ids}")
        print(f"charPr IDs     : {cp_ids}")
        print(f"paraPr IDs     : {pp_ids}")

        missing_bf = [i for i in range(1, 18) if str(i) not in bf_ids]
        missing_cp = [i for i in range(0, 21) if str(i) not in cp_ids]
        if missing_bf:
            print(f"[경고] 누락된 borderFill: {missing_bf}")
        else:
            print("✓ borderFill 1-17 모두 정상")
        if missing_cp:
            print(f"[경고] 누락된 charPr: {missing_cp}")
        else:
            print("✓ charPr 0-20 모두 정상")

    finally:
        shutil.rmtree(tmp_dir)


if __name__ == "__main__":
    main()
