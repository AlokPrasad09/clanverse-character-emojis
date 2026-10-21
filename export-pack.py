# SPDX-License-Identifier: MIT
"""Export clean character PNGs and brand only the finished preview maps."""
import base64, html, json
from pathlib import Path
from PIL import Image, ImageDraw
from add_watermark import load_font, watermark_previews

root = Path(__file__).parent
expressions = json.loads((root / 'expressions.json').read_text(encoding='utf-8'))
characters = [('archer', 'Archer', '🏹'), ('barbarian', 'Barbarian', '⚔️')]
report = []
manifest = {'name': 'Clanverse Archer & Barbarian', 'style': 'soft 3D character emojis', 'total': 48, 'packs': []}

for char, title, tab_icon in characters:
    items = []
    for index, e in enumerate(expressions, 1):
        file = f'{index:02d}-{e["id"]}'
        source = root / char / (file + '-master.png')
        if not source.exists():
            raise FileNotFoundError(str(source))
        master = Image.open(source).convert('RGBA')
        alpha = master.getchannel('A')
        if alpha.getextrema()[0] != 0 or alpha.getextrema()[1] == 0:
            raise ValueError(f'{char}/{file}: missing transparency or empty image')
        if not alpha.getbbox():
            raise ValueError(f'{char}/{file}: no visible artwork')
        # Only export scale changes: preserve generated composition and transparency.
        for size in (128, 512):
            image = master.copy()
            image.thumbnail((size, size), Image.Resampling.LANCZOS)
            square = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            square.alpha_composite(image, ((size-image.width)//2, (size-image.height)//2))
            square.save(root / char / f'{file}-{size}.png')
        items.append({'id': e['id'], 'file': file, 'name': title + ' ' + e['name'],
                      'fallback': e['glyph'], 'keywords': [char] + e['keywords'],
                      'alias': f':{char}_{e["id"].replace("-", "_")}:'})
        report.append({'character': char, 'expression': e['id'], 'masterSize': list(master.size),
                       'alphaRange': list(alpha.getextrema()), 'exports': [128,512]})
    pack = {'id': char, 'name': title, 'icon': tab_icon, 'dir': char, 'format': 'png',
            'thumbSuffix': '-128.png', 'fullSuffix': '-512.png', 'items': items}
    manifest['packs'].append(pack)
    (root / f'{char}-pack.json').write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding='utf-8')

(root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
(root / 'validation.json').write_text(json.dumps({'count': len(report), 'assets': report}, indent=2), encoding='utf-8')

font = load_font

def preview(char, title):
    width, height = 1280, 1130
    canvas = Image.new('RGB', (width, height), '#0A0E13')
    draw = ImageDraw.Draw(canvas)
    draw.text((40,24), 'CLANVERSE / CHARACTER EMOJIS', font=font(14,True), fill='#F2C65A')
    draw.text((40,55), title + ' — 24 expressions', font=font(38,True), fill='#F3F5F7')
    draw.text((40,109), 'Soft 3D · transparent PNG · 128px thumbnails + 512px artwork', font=font(15), fill='#B5BEC8')
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="1280" height="1130" fill="#0A0E13"/>',
             '<text x="40" y="40" fill="#F2C65A" font-family="Segoe UI,Arial" font-size="14">CLANVERSE / CHARACTER EMOJIS</text>',
             f'<text x="40" y="94" fill="#F3F5F7" font-family="Segoe UI,Arial" font-size="38" font-weight="600">{title} — 24 expressions</text>']
    for i,e in enumerate(expressions):
        x, y = 40+(i%6)*202, 156+(i//6)*238
        w,h=190,224
        draw.rounded_rectangle((x,y,x+w,y+h),radius=14,fill='#11171E')
        parts.append(f'<rect x="{x}" y="{y}" width="190" height="224" rx="14" fill="#11171E"/>')
        file=f'{i+1:02d}-{e["id"]}'
        image=Image.open(root/char/(file+'-512.png')).convert('RGBA')
        image.thumbnail((164,164),Image.Resampling.LANCZOS)
        ix,iy=x+13,y+10
        canvas.paste(image,(ix,iy),image)
        label=e['name']
        txtfont=font(14,True)
        textw=draw.textbbox((0,0),label,font=txtfont)[2]
        tx,ty=x+(w-textw)//2,y+184
        draw.text((tx,ty),label,font=txtfont,fill='#F3F5F7')
        data=base64.b64encode((root/char/(file+'-512.png')).read_bytes()).decode('ascii')
        parts.append(f'<g id="{char}-{e["id"]}"><image x="{ix}" y="{iy}" width="164" height="164" xlink:href="data:image/png;base64,{data}"/><text x="{tx}" y="{ty+17}" fill="#F3F5F7" font-family="Segoe UI,Arial" font-size="14">{html.escape(label)}</text></g>')
    canvas.save(root/(char+'-preview.png'))
    parts.append('</svg>')
    (root/(char+'-Figma-import.svg')).write_text('\n'.join(parts),encoding='utf-8')
    return canvas

sheets=[preview(char,title) for char,title,_ in characters]
compact=Image.new('RGB',(1280,1130*2),'#0A0E13')
compact.paste(sheets[0],(0,0));compact.paste(sheets[1],(0,1130))
compact.save(root/'complete-preview.png')
# Brand only completed root PNG maps. The character PNGs and embedded SVG
# artwork remain untouched; the combined map receives exactly one tag.
watermarked = watermark_previews(root)
(root/'state.json').write_text(json.dumps({'scope':'24 expressions per character, 48 assets','status':'complete',
 'characters':['archer','barbarian'],'completed':report,'generationMode':'built-in image_gen'},indent=2),encoding='utf-8')
print(json.dumps({'count':len(report),'packs':2,'transparent':True,'exportSizes':[128,512],
                  'watermarked':watermarked}))
