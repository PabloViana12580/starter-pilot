"""F7 images: owner originals in src/images become web-sized copies with credits."""

import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

try:
    from PIL import Image
except ImportError:  # Pillow is a development dependency
    Image = None


class OptimizeImagesTests(SimpleTestCase):
    def setUp(self):
        if Image is None:
            self.skipTest('Pillow is not installed (pip install -r requirements-dev.txt).')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / 'src'
        self.output = Path(self.tmp.name) / 'img'
        self.source.mkdir()
        settings_override = override_settings(IMAGES_SOURCE_DIR=self.source, IMAGES_OUTPUT_DIR=self.output)
        settings_override.enable()
        self.addCleanup(settings_override.disable)

    def run_command(self):
        out = StringIO()
        call_command('optimize_images', stdout=out)
        return out.getvalue()

    def test_large_photo_is_resized_to_webp_without_metadata(self):
        exif = Image.Exif()
        exif[0x010F] = 'PhoneMaker'  # camera make, standing in for GPS and other metadata
        Image.new('RGB', (3000, 1500), 'green').save(self.source / 'Front Door.JPG', exif=exif.tobytes())
        self.run_command()
        with Image.open(self.output / 'front-door.webp') as result:
            self.assertEqual(result.size, (2000, 1000))
            self.assertEqual(len(result.getexif()), 0)

    def test_credits_list_owner_images_and_are_rewritten_not_duplicated(self):
        Image.new('RGBA', (100, 100)).save(self.source / 'logo.png')
        self.run_command()
        self.run_command()
        credits = (self.output / 'CREDITS.md').read_text(encoding='utf-8')
        self.assertEqual(credits.count('`logo.webp`'), 1)
        self.assertIn('Owner-provided; all rights reserved', credits)

    def test_empty_folder_is_reported(self):
        self.assertIn('No images', self.run_command())
