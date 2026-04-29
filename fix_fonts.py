"""
base_new.hwpx 폰트 수정 스크립트
- 휴먼명조(id=4), 한양중고딕(id=5) 폰트 추가
- charPr 11,12,14 → 휴먼명조(4), charPr 13 → 한양중고딕(5) 수정
"""
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

TEMPLATE = Path("templates/base_new.hwpx")
BACKUP   = Path("templates/base_new.hwpx.bak3")

# 추가할 폰트 엔트리 (모든 fontface에 동일하게 삽입)
FONT_4 = '<hh:font id="4" face="휴먼명조" type="TTF" isEmbedded="0"><hh:typeInfo familyType="FCAT_GOTHIC" weight="5" proportion="4" contrast="0" strokeVariation="1" armStyle="1" letterform="1" midline="1" xHeight="1"/>'
FONT_5 = '<hh:font id="5" face="한양중고딕" type="HFT" isEmbedded="0"><hh:typeInfo familyType="FCAT_GOTHIC" weight="0" proportion="0" contrast="0" strokeVariation="0" armStyle="0" letterform="0" midline="0" xHeight="0"/>'

NEW_FONTS = FONT_4 + FONT_5


def fix_charpr_fontref(hdr: str, cid: str, new_font: str) -> str:
    """charPr id=cid 의 모든 fontRef 속성을 new_font 로 교체"""
    pattern = f'<hh:charPr id="{cid}"'
    idx = hdr.find(pattern)
    if idx < 0:
        print(f"  [경고] charPr id={cid} 없음")
        return hdr
    end = hdr.find("</hh:charPr>", idx) + len("</hh:charPr>")
    block = hdr[idx:end]
    # fontRef 의 모든 lang 속성을 new_font 로 교체
    def replace_fontref(m):
        return re.sub(
            r'(hangul|latin|hanja|japanese|other|symbol|user)="(\d+)"',
            lambda mm: f'{mm.group(1)}="{new_font}"',
            m.group(0)
        )
    new_block = re.sub(r'<hh:fontRef[^/]*/>', replace_fontref, block)
    return hdr[:idx] + new_block + hdr[end:]


def main():
    shutil.copy2(TEMPLATE, BACKUP)
    print(f"백업: {BACKUP}")

    tmp_dir = Path(tempfile.mkdtemp())
    try:
        with zipfile.ZipFile(TEMPLATE, "r") as z:
            z.extractall(tmp_dir)

        hdr_path = tmp_dir / "Contents" / "header.xml"
        hdr = hdr_path.read_bytes().decode("utf-8")

        # ── 1) 각 fontface 에 폰트 4,5 삽입 ──────────────────────────────
        # 각 </hh:fontface> 직전에 삽입
        count = 0
        while True:
            idx = hdr.find("</hh:fontface>", hdr.find("</hh:fontface>") if count == 0 else idx + 1)
            # fontface 태그 순서대로 처리
            all_ends = [m.start() for m in re.finditer(r"</hh:fontface>", hdr)]
            if not all_ends:
                break
            # 역순으로 삽입 (인덱스 밀림 방지)
            for pos in reversed(all_ends):
                hdr = hdr[:pos] + NEW_FONTS + hdr[pos:]
            break
        print(f"  폰트 4,5 삽입 완료 ({len(all_ends)}개 fontface)")

        # ── 2) fontCnt 4 → 6 ──────────────────────────────────────────────
        hdr = hdr.replace('fontCnt="4"', 'fontCnt="6"')
        print("  fontCnt: 4 → 6")

        # ── 3) charPr fontRef 수정 ─────────────────────────────────────────
        # 11,12,14 → 휴먼명조(4)
        for cid in ["11", "12", "14"]:
            hdr = fix_charpr_fontref(hdr, cid, "4")
            print(f"  charPr {cid} → 휴먼명조(font 4)")
        # 13 → 한양중고딕(5)
        hdr = fix_charpr_fontref(hdr, "13", "5")
        print("  charPr 13 → 한양중고딕(font 5)")

        hdr_path.write_bytes(hdr.encode("utf-8"))

        # ── 4) 재압축 ─────────────────────────────────────────────────────
        TEMPLATE.unlink()
        with zipfile.ZipFile(TEMPLATE, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(tmp_dir.rglob("*")):
                if f.is_file():
                    z.write(f, f.relative_to(tmp_dir))
        print(f"재압축 완료: {TEMPLATE}")

        # ── 5) 검증 ───────────────────────────────────────────────────────
        with zipfile.ZipFile(TEMPLATE) as z:
            h = z.read("Contents/header.xml").decode("utf-8")

        fonts = re.findall(r'<hh:font id="(\d+)" face="([^"]+)"', h)
        # 중복 제거 (fontface 7개라 동일 이름 반복)
        seen = {}
        for fid, fname in fonts:
            if fid not in seen:
                seen[fid] = fname

        print("\n── 검증 결과 ──")
        for fid in sorted(seen, key=int):
            print(f"  font id={fid}: {seen[fid]}")

        # charPr 11,13 fontRef 확인
        for cid in ["11", "13"]:
            m = re.search(f'<hh:charPr id="{cid}".*?</hh:charPr>', h, re.DOTALL)
            if m:
                fr = re.search(r'hangul="(\d+)"', m.group(0))
                print(f"  charPr {cid} hangul fontRef = {fr.group(1) if fr else '?'}")

    finally:
        shutil.rmtree(tmp_dir)


if __name__ == "__main__":
    main()
