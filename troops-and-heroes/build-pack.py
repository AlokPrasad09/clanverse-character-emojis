#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export the comedy troops and heroic heroes without changing source masters."""

import hashlib
import json
import math
import os
import shutil
import tempfile
import zipfile
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

ROOT = Path(__file__).resolve().parent


def write_json(name, value):
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")


def font(size, bold=False):
    for name in ("C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
                 "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
                 "/System/Library/Fonts/Supplemental/Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def build():
    plan = json.loads((ROOT / "sticker-plan.json").read_text(encoding="utf-8"))
    items = plan["stickers"]
    counts = Counter(item["character"] for item in items)
    if len(items) != 30 or len(counts) != 10 or set(counts.values()) != {3}:
        raise ValueError("Expected exactly three stickers for each of ten characters")
    if len({item["file"] for item in items}) != 30:
        raise ValueError("Sticker filename stems must be unique")
    # Check every input before replacing generated outputs.
    for item in items:
        path = ROOT / (item["file"] + "-master.png")
        if not path.resolve().is_relative_to(ROOT) or path.is_symlink():
            raise ValueError(f"Source must stay inside this pack: {path}")
        with Image.open(path) as master:
            master.load()
            if master.mode != "RGBA" or master.getchannel("A").getextrema() != (0, 255):
                raise ValueError(f"Expected a nonempty transparent RGBA master: {path}")
    for name in ("README.md", "LICENSE", "requirements.txt"):
        if not (ROOT / name).is_file():
            raise FileNotFoundError(ROOT / name)

    packs, report = {}, []
    for item in items:
        source = ROOT / (item["file"] + "-master.png")
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        with Image.open(source) as image:
            master = image.convert("RGBA")
        for size in (128, 512):
            # Trim only fully empty alpha margins, then leave a consistent
            # 6% clear border on each side. No visible artwork is cropped.
            resized = master.crop(master.getchannel("A").getbbox())
            content_size = round(size * 0.88)
            resized.thumbnail((content_size, content_size), Image.Resampling.LANCZOS)
            square = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            square.alpha_composite(resized, ((size - resized.width) // 2,
                                            (size - resized.height) // 2))
            square.save(ROOT / (item["file"] + f"-{size}.png"))
            # Old message URLs and previously shared download links should also
            # receive the corrected pixels, while the picker uses a fresh URL.
            for legacy in item.get("legacyFiles", []):
                if Path(legacy).name != legacy:
                    raise ValueError("Legacy filenames must be bare stems")
                shutil.copy2(ROOT / (item["file"] + f"-{size}.png"),
                             ROOT / item["character"] / f"{legacy}-{size}.png")
        character = item["character"]
        pack = packs.setdefault(character, {
            "id": character, "name": item["characterName"], "category": item["category"],
            "dir": character, "format": "png", "thumbSuffix": "-128.png",
            "fullSuffix": "-512.png", "items": [],
        })
        pack["items"].append({
            "id": item["id"], "file": Path(item["file"]).name,
            "name": f'{item["characterName"]} — {item["label"]}',
            "fallback": "😆" if item["category"] == "comedy" else "⚔️",
            "keywords": [character, item["category"], *item["id"].split("-")],
            "alias": f':{character.replace("-", "_")}_{item["id"].replace("-", "_")}:',
            **({"legacyFiles": item["legacyFiles"]} if item.get("legacyFiles") else {}),
        })
        report.append({"character": character, "id": item["id"],
                       "master": item["file"] + "-master.png",
                       "masterSize": list(master.size), "masterSHA256": source_hash,
                       "alphaRange": list(master.getchannel("A").getextrema()),
                       "exports": [128, 512], "contentFraction": 0.88})
        if hashlib.sha256(source.read_bytes()).hexdigest() != source_hash:
            raise ValueError(f"Master changed during export: {source}")

    manifest = {"name": plan["name"], "style": "soft 3D character stickers",
                "total": len(items), "categories": {"comedy": 12, "heroic": 18},
                "packs": list(packs.values())}
    write_json("manifest.json", manifest)
    write_json("validation.json", {"count": len(report), "assets": report})
    write_json("generation-state.json", {
        "status": "complete", "generationMode": "built-in image_gen",
        "stickers": len(items), "characters": len(packs),
        "categories": manifest["categories"],
        "masters": [asset["master"] for asset in report],
    })
    for character, pack in packs.items():
        write_json(f"{character}-pack.json", pack)

    # This one aggregation map is the ONLY branded image. Raw assets stay clean.
    width, columns, step = 1280, 6, 240
    height = 130 + math.ceil(len(items) / columns) * step + 50
    board = Image.new("RGBA", (width, height), "#0A0E13")
    draw = ImageDraw.Draw(board)
    draw.text((28, 22), "CLANVERSE / TROOPS & HEROES", font=font(15, True), fill="#F2C65A")
    draw.text((28, 50), "12 comedy troops + 18 heroic heroes", font=font(32, True), fill="#F3F5F7")
    draw.text((28, 94), "Three unique poses per character · transparent PNG · 128px + 512px",
              font=font(15), fill="#B5BEC8")
    for index, item in enumerate(items):
        x, y = 28 + (index % columns) * 204, 130 + (index // columns) * step
        draw.rounded_rectangle((x, y, x + 194, y + 226), radius=14, fill="#11171E")
        with Image.open(ROOT / (item["file"] + "-512.png")) as image:
            sticker = image.convert("RGBA")
        sticker.thumbnail((168, 168), Image.Resampling.LANCZOS)
        board.alpha_composite(sticker, (x + (194 - sticker.width) // 2, y + 5))
        for label, line_y, size, color in (
            (item["characterName"], y + 178, 13, "#F2C65A"),
            (item["label"], y + 200, 12, "#F3F5F7"),
        ):
            text_font = font(size, True)
            box = draw.textbbox((0, 0), label, font=text_font)
            draw.text((x + (194 - box[2] + box[0]) // 2, line_y), label,
                      font=text_font, fill=color)
    overlay = Image.new("RGBA", board.size, (0, 0, 0, 0))
    tag_draw = ImageDraw.Draw(overlay)
    tag, tag_font = "Powered by Clanverse App", font(16, True)
    left, top, right, bottom = tag_draw.textbbox((0, 0), tag, font=tag_font)
    tag_width, tag_height = right - left + 24, bottom - top + 12
    x, y = width - tag_width - 16, height - tag_height - 14
    tag_draw.rounded_rectangle((x, y, x + tag_width, y + tag_height), radius=7,
                               fill=(17, 23, 30, 190))
    tag_draw.text((x + 12 - left, y + 6 - top), tag, font=tag_font, fill=(242, 198, 90, 225))
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("ClanversePreviewWatermark", "1")
    Image.alpha_composite(board, overlay).convert("RGB").save(
        ROOT / "complete-preview.png", pnginfo=metadata)

    names = ["README.md", "LICENSE", "requirements.txt", "build-pack.py",
             "sticker-plan.json", "manifest.json", "validation.json", "generation-state.json",
             "complete-preview.png"]
    names += [f"{character}-pack.json" for character in packs]
    names += [item["file"] + f"-{size}.png" for item in items for size in (128, 512)]
    names += [f'{item["character"]}/{legacy}-{size}.png' for item in items
              for legacy in item.get("legacyFiles", []) for size in (128, 512)]
    output = ROOT / "Clanverse-Troops-Comedy-Heroes-30.zip"
    with tempfile.NamedTemporaryFile(dir=ROOT, prefix=".pack-", suffix=".zip", delete=False) as temp:
        temporary = Path(temp.name)
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for name in names:
                archive.write(ROOT / name, name)
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None or set(archive.namelist()) != set(names):
                raise ValueError("Archive validation failed")
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps({"stickers": len(items), "packs": len(packs), "runtimePNGs": 60,
                      "mastersPreserved": 30, "archive": str(output), "archiveFiles": len(names)}))


if __name__ == "__main__":
    build()
