#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Brand only the three root preview maps; never traverse character folders."""

import json
import os
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

PREVIEW_NAMES = (
    "complete-preview.png",
    "archer-preview.png",
    "barbarian-preview.png",
)
WATERMARK_TEXT = "Powered by Clanverse App"
WATERMARK_KEY = "ClanversePreviewWatermark"
WATERMARK_VERSION = "1"


def load_font(size, bold=False):
    """Use an available system font, with Pillow's portable font as fallback."""
    candidates = (
        "C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def watermark_previews(root):
    """Apply one bottom-right translucent tag to each allowlisted root PNG.

    The fixed allowlist, direct-child check, and symlink/hard-link rejection
    prevent redirecting a preview write into an operational character asset.
    A PNG text marker makes repeat calls byte-for-byte idempotent. Regenerate
    previews with export-pack.py to change the tag style or replace metadata.
    """
    root = Path(root).resolve(strict=True)
    targets = [root / name for name in PREVIEW_NAMES]
    # Validate all paths before any mutation. There is deliberately no glob,
    # recursive traversal, arbitrary image argument, or output path option.
    for path in targets:
        if path.is_symlink() or path.resolve(strict=True).parent != root:
            raise ValueError(f"Preview must be a direct, non-symlink file: {path}")
        if not path.is_file() or path.stat().st_nlink != 1:
            raise ValueError(f"Preview must be a regular, unshared file: {path}")
        with Image.open(path) as source:
            if source.format != "PNG" or min(source.size) < 320:
                raise ValueError(f"Expected a PNG preview at least 320px wide/high: {path}")

    changed = []
    for path in targets:
        with Image.open(path) as source:
            if source.info.get(WATERMARK_KEY) == WATERMARK_VERSION:
                continue
            original_mode = source.mode
            original_info = source.info.copy()
            canvas = source.convert("RGBA")

        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        font = load_font(max(12, round(canvas.width / 80)), bold=True)
        left, top, right, bottom = draw.textbbox((0, 0), WATERMARK_TEXT, font=font)
        margin, padding_x, padding_y = 8, 12, 6
        width, height = right - left + 2 * padding_x, bottom - top + 2 * padding_y
        if width + 2 * margin > canvas.width:
            raise ValueError(f"Preview is too narrow for the watermark: {path}")
        x, y = canvas.width - margin - width, canvas.height - margin - height
        draw.rounded_rectangle((x, y, x + width, y + height), radius=7,
                               fill=(17, 23, 30, 190))
        draw.text((x + padding_x - left, y + padding_y - top), WATERMARK_TEXT,
                  font=font, fill=(242, 198, 90, 225))
        result = Image.alpha_composite(canvas, overlay)
        if original_mode == "RGB":
            result = result.convert("RGB")
        metadata = PngImagePlugin.PngInfo()
        for key, value in original_info.items():
            if isinstance(value, str):
                metadata.add_itxt(key, value)
        metadata.add_text(WATERMARK_KEY, WATERMARK_VERSION)
        options = {key: original_info[key] for key in ("icc_profile", "dpi")
                   if key in original_info}
        # Replace only after a complete successful encode; leave no partial PNG.
        with tempfile.NamedTemporaryFile(dir=root, prefix=".preview-", suffix=".png",
                                         delete=False) as temporary:
            temporary_path = Path(temporary.name)
        try:
            result.save(temporary_path, format="PNG", pnginfo=metadata, **options)
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)
        changed.append(path.name)
    return changed


if __name__ == "__main__":
    print(json.dumps({"watermarked": watermark_previews(Path(__file__).parent)}))
