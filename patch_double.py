"""borderFill id=7,8의 DOUBLE bottom width를 0.12mm → 0.4mm로 수정"""
import zipfile, shutil, re
from pathlib import Path

template = Path('templates/base_new.hwpx')
work_dir = Path('temp_patch_double')
if work_dir.exists():
    shutil.rmtree(work_dir)
work_dir.mkdir()

with zipfile.ZipFile(template, 'r') as zf:
    zf.extractall(work_dir)

header_path = work_dir / 'Contents' / 'header.xml'
header = header_path.read_text(encoding='utf-8')

# id=7, 8 의 bottomBorder DOUBLE width 0.12mm → 0.4mm
def fix_double_width(text, bid):
    pattern = rf'(<hh:borderFill id="{bid}".*?bottomBorder type="DOUBLE" width=")0\.12 mm(".*?</hh:borderFill>)'
    return re.sub(pattern, r'\g<1>0.4 mm\g<2>', text, flags=re.DOTALL)

header = fix_double_width(header, '7')
header = fix_double_width(header, '8')

# 검증
for bid in ['7', '8']:
    m = re.search(rf'<hh:borderFill id="{bid}".*?</hh:borderFill>', header, re.DOTALL)
    if m:
        bottom = re.search(r'bottomBorder[^/]+/', m.group())
        print(f'borderFill id={bid} bottom: {bottom.group() if bottom else None}')

header_path.write_text(header, encoding='utf-8')

with zipfile.ZipFile(template, 'w', zipfile.ZIP_DEFLATED) as zf:
    for f in work_dir.rglob('*'):
        if f.is_file():
            zf.write(f, f.relative_to(work_dir))

shutil.rmtree(work_dir)
print('완료')
