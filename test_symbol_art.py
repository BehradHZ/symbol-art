import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageOps

from symbol_art import convert


class ConversionTests(unittest.TestCase):
    def test_columns_and_proportions(self):
        art = convert(Image.new("RGB", (100, 150), "gray"))
        self.assertEqual(len(art.splitlines()), 30)
        self.assertTrue(all(len(line) == 40 for line in art.splitlines()))
        self.assertTrue(art.isascii())

    def test_flat_white_is_empty(self):
        self.assertEqual(set(convert(Image.new("RGB", (60, 60), "white"))), {" ", "\n"})

    def test_flat_black_is_dense(self):
        art = convert(Image.new("RGB", (60, 60), "black"))
        self.assertNotIn(" ", art)
        self.assertEqual(len(set(art.replace("\n", ""))), 1)

    def test_inversion(self):
        image = Image.linear_gradient("L").resize((80, 80))
        # Isolate polarity from Pillow's integer-rounded contrast adjustment.
        options = {"contrast": 1, "autocontrast": False}
        self.assertEqual(convert(image, invert=True, **options), convert(ImageOps.invert(image), **options))

    def test_transparency_is_empty_in_both_polarities(self):
        image = Image.new("RGBA", (60, 60), (180, 10, 120, 0))
        for invert in (False, True):
            self.assertEqual(set(convert(image, invert=invert)), {" ", "\n"})

    def test_crop_and_height(self):
        art = convert(Image.new("RGB", (100, 100)), 20, crop=(0, 0, 40, 80))
        self.assertEqual(len(art.splitlines()), 20)
        self.assertEqual(len(convert(Image.new("L", (100, 100)), height=7).splitlines()), 7)

    def test_exif_orientation(self):
        image = Image.new("RGB", (60, 120))
        image.getexif()[274] = 6
        self.assertEqual(len(convert(image).splitlines()), 10)

    def test_invalid_options(self):
        for options in ({"width": 0}, {"width": 501}, {"gamma": 0}, {"gamma": float("nan")},
                        {"height": 0}, {"cell_aspect": float("inf")}, {"crop": (0, 0, 999, 10)}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                convert(Image.new("L", (30, 30)), **options)

    def test_cli_output_and_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output, preview = root / "input photo.png", root / "art.txt", root / "art.png"
            Image.linear_gradient("L").save(source)
            process = subprocess.run([sys.executable, str(Path(__file__).with_name("symbol_art.py")),
                                      str(source), "-w", "40", "-o", str(output), "--preview", str(preview)],
                                     capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(process.stdout, output.read_text(encoding="ascii"))
            self.assertTrue(all(len(line) == 40 for line in process.stdout.splitlines()))
            with Image.open(preview) as image:
                image.verify()

    def test_cli_missing_image(self):
        process = subprocess.run([sys.executable, str(Path(__file__).with_name("symbol_art.py")),
                                  "missing-image-123456.png"], capture_output=True, text=True)
        self.assertEqual(process.returncode, 2)
        self.assertIn("Error:", process.stderr)
        self.assertNotIn("Traceback", process.stderr)


if __name__ == "__main__":
    unittest.main()
