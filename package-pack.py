# SPDX-License-Identifier: MIT
"""Build the runtime distribution with its license and engineering utilities."""
import json
import zipfile
from pathlib import Path
from add_watermark import watermark_previews

root = Path(__file__).parent
expressions = json.loads((root / 'expressions.json').read_text(encoding='utf-8'))
files = []
for character in ('archer', 'barbarian'):
    for number, expression in enumerate(expressions, 1):
        for size in (128, 512):
            files.append(root / character / f'{number:02d}-{expression["id"]}-{size}.png')
files += [root / name for name in (
    'README.md', 'LICENSE', 'requirements.txt', '.gitignore',
    'branding/clanverse-logo-light.svg', 'branding/clanverse-logo-dark.svg',
    'export-pack.py', 'package-pack.py', 'read-catalog.py', 'add_watermark.py',
    'validate-pack.py', 'test_tools.py',
    'expressions.json', 'prompts.json', 'manifest.json',
    'manifest-plan.json', 'smiley-catalog.json',
    'archer-pack.json', 'barbarian-pack.json', 'validation.json',
    'archer-preview.png', 'barbarian-preview.png', 'complete-preview.png',
    'archer-Figma-import.svg', 'barbarian-Figma-import.svg',
)]
missing = [str(path.relative_to(root)) for path in files if not path.exists()]
if missing:
    raise FileNotFoundError(missing)
# Ensure packaged review maps are branded even when packaging is run directly.
watermark_previews(root)
output = root / 'Clanverse-Archer-Barbarian-48.zip'
with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for path in files:
        archive.write(path, str(path.relative_to(root)))
with zipfile.ZipFile(output) as archive:
    corrupt = archive.testzip()
    if corrupt is not None:
        raise ValueError(f'Corrupt archive member: {corrupt}')
    expected = {path.relative_to(root).as_posix() for path in files}
    if set(archive.namelist()) != expected or len(archive.namelist()) != len(files):
        raise ValueError('Archive membership differs from the package file list')
print(json.dumps({'archive': str(output), 'files': len(files), 'bytes': output.stat().st_size}))
