#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate runtime mappings, the expression plan, and transparent PNGs."""

import argparse
import json
from pathlib import Path

from PIL import Image

from add_watermark import PREVIEW_NAMES, WATERMARK_KEY, WATERMARK_VERSION


def validate(root, require_masters=False):
    def read(name):
        return json.loads((root / name).read_text(encoding="utf-8"))

    def check(condition, message):
        if not condition:
            raise ValueError(message)

    expressions = read("expressions.json")
    manifest = read("manifest.json")
    plan = read("manifest-plan.json")
    catalog = read("smiley-catalog.json")
    report = read("validation.json")
    check(len(expressions) == 24, "Expected 24 shared expression definitions")
    ids = [e["id"] for e in expressions]
    check(len(set(ids)) == 24, "Expression IDs must be unique")
    for expression in expressions:
        check(all(isinstance(expression[key], str) and expression[key]
                  for key in ("id", "glyph", "name", "description")),
              "Expression text fields must be nonempty strings")
        check(isinstance(expression["keywords"], list) and expression["keywords"]
              and all(isinstance(k, str) and k for k in expression["keywords"]),
              "Expression keywords must be a nonempty string array")
    check(len({e["glyph"] for e in catalog}) == len(catalog), "Duplicate catalog glyphs")
    check(all(isinstance(e["keywords"], str) and e["keywords"] for e in catalog),
          "Catalog keywords must be nonempty strings")
    check({e["glyph"] for e in expressions} <= {e["glyph"] for e in catalog},
          "An expression fallback glyph is missing from the Unicode catalog")
    check(manifest["total"] == 48 and len(manifest["packs"]) == 2,
          "Manifest must contain two packs totaling 48 entries")
    packs = {pack["id"]: pack for pack in manifest["packs"]}
    check(set(packs) == {"archer", "barbarian"}, "Unexpected character pack IDs")
    expected_plan, assets, aliases, master_sizes = {}, {}, set(), set()
    png_count, master_count = 0, 0
    for character, title in (("archer", "Archer"), ("barbarian", "Barbarian")):
        pack = packs[character]
        check(pack == read(f"{character}-pack.json"), f"{character} pack differs from manifest")
        check(pack["dir"] == character and pack["format"] == "png"
              and pack["thumbSuffix"] == "-128.png" and pack["fullSuffix"] == "-512.png",
              f"{character}: invalid runtime path parameters")
        check([item["id"] for item in pack["items"]] == ids,
              f"{character}: expression order or IDs differ")
        for number, (expression, item) in enumerate(zip(expressions, pack["items"]), 1):
            stem = f'{number:02d}-{expression["id"]}'
            key = (character, expression["id"])
            alias = f':{character}_{expression["id"].replace("-", "_")}:'
            check(item["file"] == stem and item["fallback"] == expression["glyph"]
                  and item["name"] == f'{title} {expression["name"]}'
                  and item["keywords"] == [character] + expression["keywords"]
                  and item["alias"] == alias and alias not in aliases,
                  f"{character}/{stem}: inconsistent runtime mapping")
            aliases.add(alias)
            expected_plan[key] = {"character": character, "expression": expression["id"],
                                  "number": number, "file": f"{character}/{stem}",
                                  "name": expression["name"], "glyph": expression["glyph"],
                                  "keywords": expression["keywords"]}
            for size in (128, 512):
                path = root / character / f"{stem}-{size}.png"
                with Image.open(path) as image:
                    image.load()
                    check(image.format == "PNG" and image.mode == "RGBA"
                          and image.size == (size, size), f"Invalid PNG export: {path}")
                    check(image.getchannel("A").getextrema() == (0, 255),
                          f"Missing transparency or opaque artwork: {path}")
                    check(WATERMARK_KEY not in image.info, f"Watermarked raw asset: {path}")
                png_count += 1
            master = root / character / f"{stem}-master.png"
            if require_masters or master.exists():
                with Image.open(master) as image:
                    image.load()
                    check(image.mode == "RGBA" and image.getchannel("A").getextrema() == (0, 255),
                          f"Invalid transparent master: {master}")
                    master_sizes.add(image.size)
                    assets[key] = {"character": character, "expression": expression["id"],
                                   "masterSize": list(image.size), "alphaRange": [0, 255],
                                   "exports": [128, 512]}
                master_count += 1
    check(len(plan) == 48 and {(p["character"], p["expression"]): p for p in plan} == expected_plan,
          "Manifest plan differs from runtime mappings")
    check(report["count"] == 48 and len(report["assets"]) == 48,
          "Validation report count is stale")
    actual_assets = {(a["character"], a["expression"]): a for a in report["assets"]}
    check(set(actual_assets) == set(expected_plan), "Validation report contains mismatched assets")
    check(all(actual_assets[key] == asset for key, asset in assets.items()),
          "Validation report differs from observed masters")
    for name in PREVIEW_NAMES:
        with Image.open(root / name) as image:
            image.load()
            expected_size = (1280, 2260) if name == "complete-preview.png" else (1280, 1130)
            check(image.size == expected_size, f"Incorrect preview dimensions: {name}")
            check(image.info.get(WATERMARK_KEY) == WATERMARK_VERSION,
                  f"Missing preview watermark marker: {name}")
    return {"status": "valid", "expressions": len(expressions), "characterAssets": 48,
            "runtimePNGs": png_count, "mastersChecked": master_count,
            "masterSizes": sorted(master_sizes), "catalogEntries": len(catalog),
            "previewMaps": len(PREVIEW_NAMES)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-masters", action="store_true",
                        help="Require all 48 master sources (not included in the runtime ZIP)")
    args = parser.parse_args()
    try:
        print(json.dumps(validate(Path(__file__).resolve().parent, args.require_masters)))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Validation failed: {error}\n")
