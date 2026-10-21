# SPDX-License-Identifier: MIT
"""Refresh the Unicode reference catalog from the optional app checkout."""
import argparse
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path,
                    default=root.parent.parent / 'clanverse-web/src/lib/emoji/unicode.ts',
                    help='Path to the app Unicode TypeScript catalog')
args = parser.parse_args()
if not args.source.is_file():
    parser.error('Unicode source is unavailable; use --source PATH or keep the bundled smiley-catalog.json')
source = args.source.read_text(encoding='utf-8')
category = re.search(r'\bid:\s*"smileys".*?\bitems:\s*\[(.*?)\]\s*\}', source, re.S)
if not category:
    parser.error('Smileys category format was not recognized; catalog was not changed')
block = category.group(1)
items = [{'glyph': g, 'keywords': k} for g, k in re.findall(r'\["([^"]+)", "([^"]+)"\]', block)]
if not items or len({item['glyph'] for item in items}) != len(items):
    parser.error('Smileys category is empty or has duplicate glyphs; catalog was not changed')
Path(__file__).with_name('smiley-catalog.json').write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'count': len(items), 'output': str(root / 'smiley-catalog.json')}))
