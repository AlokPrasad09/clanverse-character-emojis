#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Sync clean character exports and troop/hero registries into the local apps."""

import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent.parent
ICONS = {
    "dragon": "🐉", "wizard": "🧙", "hog-rider": "🐗", "bowler": "🪨",
    "barbarian-king": "👑", "archer-queen": "👑", "grand-warden": "🔮",
    "royal-champion": "🛡️", "minion-prince": "🦇", "dragon-duke": "🐲",
}


def quoted(value):
    return json.dumps(value, ensure_ascii=False)


def generated_block(path, name, body, anchor, prefix="//"):
    start, end = f"{prefix} BEGIN {name}", f"{prefix} END {name}"
    block = f"{start}\n{body}\n{end}\n\n"
    text = path.read_text(encoding="utf-8")
    pattern = re.escape(start) + r"\n.*?" + re.escape(end) + r"\n\n"
    if start in text:
        text, count = re.subn(pattern, lambda _: block, text, flags=re.S)
        if count != 1:
            raise ValueError(f"Ambiguous generated block in {path}")
    else:
        if text.count(anchor) != 1:
            raise ValueError(f"Missing or ambiguous registry anchor in {path}")
        text = text.replace(anchor, block + anchor, 1)
    path.write_text(text, encoding="utf-8")


def main():
    required_app_files = (
        WORKSPACE / "clanverse-web/src/lib/emoji/sets.ts",
        WORKSPACE / "mobile/lib/shared/emoji/emoji_catalog.dart",
        WORKSPACE / "mobile/pubspec.yaml",
    )
    if not all(path.is_file() for path in required_app_files):
        raise SystemExit("Run this utility inside the full Clanverse app checkout; "
                         "a standalone artwork repository has no app targets to synchronize.")
    base = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    extra_root = ROOT / "troops-and-heroes"
    extra = json.loads((extra_root / "manifest.json").read_text(encoding="utf-8"))
    destinations = [WORKSPACE / "clanverse-web/public/emoji",
                    WORKSPACE / "backend/public/emoji", WORKSPACE / "mobile/assets/emoji"]
    copies = []
    for source_root, manifest in ((ROOT, base), (extra_root, extra)):
        for pack in manifest["packs"]:
            for item in pack["items"]:
                for suffix in (pack["thumbSuffix"], pack["fullSuffix"]):
                    relative = Path(pack["dir"]) / (item["file"] + suffix)
                    source = source_root / relative
                    if not source.is_file():
                        raise FileNotFoundError(source)
                    copies.extend((source, destination / relative) for destination in destinations)
                    for legacy in item.get("legacyFiles", []):
                        if Path(legacy).name != legacy:
                            raise ValueError("Legacy filenames must be bare stems")
                        alias = Path(pack["dir"]) / (legacy + suffix)
                        copies.extend((source, destination / alias) for destination in destinations)
    # Preflight every source before copying; never copy masters or review maps.
    for source, destination in copies:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists() or source.read_bytes() != destination.read_bytes():
            shutil.copy2(source, destination)
    for destination in destinations:
        shutil.copy2(ROOT / "LICENSE", destination / "CLANVERSE-CHARACTER-LICENSE.txt")

    web_lines = ["// Generated from assets/clanverse-character-emojis/troops-and-heroes/manifest.json.",
                 "// Run python assets/clanverse-character-emojis/sync-app-stickers.py after rebuilding artwork.",
                 "export const EMOJI_TROOP_HERO_SETS: EmojiSet[] = ["]
    dart_lines = ["// Generated from the troop/hero manifest by sync-app-stickers.py."]
    dart_names = []
    for pack in extra["packs"]:
        web_lines.append("  {")
        for key in ("id", "name", "dir", "format", "thumbSuffix", "fullSuffix"):
            web_lines.append(f"    {key}: {quoted(pack[key])},")
        web_lines += [f'    icon: {quoted(ICONS[pack["id"]])},', "    items: ["]
        words = pack["id"].split("-")
        dart_name = words[0] + "".join(word.title() for word in words[1:]) + "ImageEmojis"
        dart_names.append((pack, dart_name))
        dart_lines.append(f"const {dart_name} = <ImageEmoji>[")
        for item in pack["items"]:
            keywords = list(dict.fromkeys(item["keywords"] + words + [item["alias"].strip(":")]))
            web_item = {key: item[key] for key in ("id", "file", "name", "fallback")}
            web_item["keywords"] = keywords
            web_lines.append("      " + quoted(web_item) + ",")
            args = ", ".join(quoted(item[key]) for key in ("id", "file", "name", "fallback"))
            # Dollar signs must be escaped in generated Dart string literals.
            dart_lines.append(f"  ImageEmoji({args}, {quoted(keywords)}, setId: {quoted(pack['id'])}),"
                              .replace("$", "\\$"))
        web_lines += ["    ],", "  },"]
        dart_lines += ["];", ""]
    web_lines.append("];")
    dart_lines.append("const troopHeroImageEmojiSets = <ImageEmojiSet>[")
    for pack, dart_name in dart_names:
        dart_lines.append(f"  ImageEmojiSet({quoted(pack['id'])}, {quoted(pack['name'])}, "
                          f"{quoted(ICONS[pack['id']])}, {dart_name}),")
    dart_lines += ["];", "", "const troopHeroImageEmojis = <ImageEmoji>["]
    dart_lines += [f"  ...{name}," for _, name in dart_names]
    dart_lines.append("];")
    generated_block(WORKSPACE / "clanverse-web/src/lib/emoji/sets.ts", "CLANVERSE TROOP HERO SETS",
                    "\n".join(web_lines), "// Brand reactions, 3D faces and character packs;")
    generated_block(WORKSPACE / "mobile/lib/shared/emoji/emoji_catalog.dart", "CLANVERSE TROOP HERO SETS",
                    "\n".join(dart_lines), "const imageEmojiSets = <ImageEmojiSet>[")

    pubspec = WORKSPACE / "mobile/pubspec.yaml"
    text = pubspec.read_text(encoding="utf-8")
    asset_lines = [f"    - assets/emoji/{pack['dir']}/" for pack in extra["packs"]]
    asset_lines.append("    - assets/emoji/CLANVERSE-CHARACTER-LICENSE.txt")
    start, end = "    # BEGIN CLANVERSE TROOP HERO ASSETS", "    # END CLANVERSE TROOP HERO ASSETS"
    block = start + "\n" + "\n".join(asset_lines) + "\n" + end + "\n"
    if start in text:
        text, count = re.subn(re.escape(start) + r"\n.*?" + re.escape(end) + r"\n",
                              lambda _: block, text, flags=re.S)
        if count != 1:
            raise ValueError("Ambiguous Flutter asset block")
    else:
        anchor = "    - assets/emoji/clanverse-3d/\n"
        if text.count(anchor) != 1:
            raise ValueError("Missing Flutter emoji asset anchor")
        text = text.replace(anchor, anchor + block, 1)
    pubspec.write_text(text, encoding="utf-8")
    print(json.dumps({"characterStickers": base["total"] + extra["total"],
                      "newPacks": len(extra["packs"]), "destinations": len(destinations),
                      "runtimeFileCopies": len(copies)}))


if __name__ == "__main__":
    main()
