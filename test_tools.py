# SPDX-License-Identifier: MIT
"""Regression checks for the watermark's asset-protection boundary."""

import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageChops

from add_watermark import PREVIEW_NAMES, WATERMARK_KEY, WATERMARK_VERSION, watermark_previews


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WatermarkTests(unittest.TestCase):
    def setUp(self):
        test_parent = Path(__file__).resolve().parent
        self.temporary = tempfile.TemporaryDirectory(dir=test_parent, prefix=".test-watermark-")
        self.root = Path(self.temporary.name).resolve()
        if self.root.parent != test_parent:
            raise ValueError("Test directory escaped its intended parent")
        self.addCleanup(self.temporary.cleanup)
        for name in PREVIEW_NAMES:
            Image.new("RGBA", (640, 480), (20, 40, 60, 180)).save(self.root / name)

    def test_only_root_maps_change_and_second_run_is_identical(self):
        for character in ("archer", "barbarian"):
            folder = self.root / character
            folder.mkdir()
            # Include a nested name matching the allowlist to catch recursion.
            for name in (*PREVIEW_NAMES, "01-happy-master.png", "01-happy-128.png"):
                Image.new("RGBA", (640, 480), (0, 0, 0, 0)).save(folder / name)
        Image.new("RGB", (640, 480), "black").save(self.root / "archer-progress.png")
        protected = {p: digest(p) for p in self.root.rglob("*.png") if p.parent != self.root
                     or p.name not in PREVIEW_NAMES}
        with Image.open(self.root / PREVIEW_NAMES[0]) as image:
            before = image.copy()
        self.assertEqual(watermark_previews(self.root), list(PREVIEW_NAMES))
        for name in PREVIEW_NAMES:
            with Image.open(self.root / name) as image:
                self.assertEqual(image.size, (640, 480))
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.info[WATERMARK_KEY], WATERMARK_VERSION)
                self.assertEqual(image.getpixel((0, 0)), (20, 40, 60, 180))
                self.assertIsNone(ImageChops.difference(before.crop((0, 0, 640, 400)),
                                                       image.crop((0, 0, 640, 400))).getbbox())
                self.assertNotEqual(image.tobytes(), before.tobytes())
        first = {name: digest(self.root / name) for name in PREVIEW_NAMES}
        self.assertEqual(watermark_previews(self.root), [])
        self.assertEqual(first, {name: digest(self.root / name) for name in PREVIEW_NAMES})
        self.assertEqual(protected, {p: digest(p) for p in protected})

    def test_missing_preview_fails_before_writing(self):
        (self.root / PREVIEW_NAMES[-1]).unlink()
        before = digest(self.root / PREVIEW_NAMES[0])
        with self.assertRaises(FileNotFoundError):
            watermark_previews(self.root)
        self.assertEqual(before, digest(self.root / PREVIEW_NAMES[0]))

    def test_symlink_cannot_redirect_a_preview_to_a_raw_asset(self):
        target = self.root / "raw.png"
        (self.root / PREVIEW_NAMES[0]).replace(target)
        try:
            (self.root / PREVIEW_NAMES[0]).symlink_to(target)
        except OSError:
            self.skipTest("This platform does not allow creating symlinks")
        before = digest(target)
        with self.assertRaises(ValueError):
            watermark_previews(self.root)
        self.assertEqual(before, digest(target))

    def test_hard_link_cannot_share_a_preview_with_a_raw_asset(self):
        target = self.root / "raw.png"
        preview = self.root / PREVIEW_NAMES[0]
        preview.replace(target)
        try:
            os.link(target, preview)
        except OSError:
            self.skipTest("This filesystem does not support hard links")
        before = digest(target)
        with self.assertRaises(ValueError):
            watermark_previews(self.root)
        self.assertEqual(before, digest(target))

    def test_shared_file_metadata_is_rejected_without_link_privileges(self):
        preview = self.root / PREVIEW_NAMES[0]
        original_stat = Path.stat

        def shared_stat(path, *args, **kwargs):
            result = original_stat(path, *args, **kwargs)
            if path == preview:
                fields = list(result)
                fields[3] = 2  # st_nlink; retain the real file type and other fields.
                return os.stat_result(fields)
            return result

        before = digest(preview)
        with patch.object(Path, "stat", shared_stat):
            with self.assertRaises(ValueError):
                watermark_previews(self.root)
        self.assertEqual(before, digest(preview))


if __name__ == "__main__":
    unittest.main()
