from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

SOURCE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.webp'}
CREDITS_START = '<!-- owner-images:start -->'
CREDITS_END = '<!-- owner-images:end -->'


class Command(BaseCommand):
    help = (
        'Writes web-sized WebP copies of the images in src/images to static/img '
        '(orientation applied, metadata such as GPS location removed) and lists '
        'them in static/img/CREDITS.md as owner-provided.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--max-width', type=int, default=2000)
        parser.add_argument('--quality', type=int, default=80)

    def handle(self, *args, max_width, quality, **options):
        try:
            from PIL import Image, ImageOps
        except ImportError as exc:
            raise CommandError('Pillow is required: pip install -r requirements-dev.txt') from exc

        source_dir = settings.IMAGES_SOURCE_DIR
        output_dir = settings.IMAGES_OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        sources = sorted(p for p in source_dir.iterdir() if p.suffix.lower() in SOURCE_SUFFIXES) if source_dir.is_dir() else []
        if not sources:
            self.stdout.write(f'No images in {source_dir}.')
            return

        written = []
        for path in sources:
            name = (slugify(path.stem) or 'image') + '.webp'
            with Image.open(path) as original:
                image = ImageOps.exif_transpose(original)
                image = image.convert('RGBA' if 'A' in image.getbands() else 'RGB')
                if image.width > max_width:
                    height = round(image.height * max_width / image.width)
                    image = image.resize((max_width, height), Image.Resampling.LANCZOS)
                # Saved without the original's EXIF/metadata.
                image.save(output_dir / name, 'WEBP', quality=quality, method=6)
                written.append((name, path.name, image.width, image.height))
            self.stdout.write(f'{path.name} -> static/img/{name} ({written[-1][2]}x{written[-1][3]})')

        self._update_credits(output_dir / 'CREDITS.md', written)
        self.stdout.write(self.style.SUCCESS(f'{len(written)} image(s) written.'))

    @staticmethod
    def _update_credits(credits_path, written):
        lines = [CREDITS_START, '', '| File | Original | Size | Source |', '| --- | --- | --- | --- |']
        lines += [
            f'| `{name}` | `src/images/{original}` | {width}x{height} | Owner-provided; all rights reserved |'
            for name, original, width, height in written
        ]
        lines += ['', CREDITS_END]
        block = '\n'.join(lines)
        text = credits_path.read_text(encoding='utf-8') if credits_path.exists() else '# Image credits\n\n'
        if CREDITS_START in text and CREDITS_END in text:
            before, rest = text.split(CREDITS_START, 1)
            after = rest.split(CREDITS_END, 1)[1]
            text = before + block + after
        else:
            text = text.rstrip('\n') + '\n\n## Owner-provided images\n\n' + block + '\n'
        credits_path.write_text(text, encoding='utf-8', newline='\n')
