import random
from io import BytesIO

from PIL import Image

from app.utils.cover_fit import content_ratio, fit_cover


def noise(width: int, height: int, seed: int = 1) -> Image.Image:
    rng = random.Random(seed)
    return Image.frombytes("L", (width, height), bytes(rng.randrange(256) for _ in range(width * height))).convert("RGB")


def encode(image: Image.Image, fmt: str = "PNG") -> bytes:
    output = BytesIO()
    image.save(output, format=fmt)
    return output.getvalue()


def size_of(contents: bytes) -> tuple[int, int]:
    with Image.open(BytesIO(contents)) as image:
        return image.size


def test_a_card_shaped_cover_is_left_alone():
    assert fit_cover(encode(noise(200, 300))) is None


def test_landscape_art_is_cropped_to_the_card_around_its_detail():
    # Flat on the left, detailed on the right: the crop lands on the detail.
    image = Image.new("RGB", (480, 270), (40, 40, 40))
    image.paste(noise(180, 270), (300, 0))
    width, height = size_of(fit_cover(encode(image, "JPEG")))
    assert height == 270 and abs(width / height - 2 / 3) < 0.01
    cropped = Image.open(BytesIO(fit_cover(encode(image))))
    assert cropped.getpixel((cropped.width - 1, 135)) != (40, 40, 40)


def test_letterboxed_art_counts_as_landscape_and_loses_its_bars():
    canvas = Image.new("RGB", (264, 352), (20, 20, 30))
    canvas.paste(noise(264, 148), (0, 102))
    assert content_ratio(encode(canvas)) > 1.5
    width, height = size_of(fit_cover(encode(canvas)))
    assert abs(width / height - 2 / 3) < 0.02 and height < 160
