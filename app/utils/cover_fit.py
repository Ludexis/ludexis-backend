"""Fits cover art to the library card's 2:3 shape.

Some sources ship landscape key art as a "cover", or pad it into a portrait canvas with blurred or flat
bars. Both look wrong on a 2:3 card, so the picture area is found first and, when it is not portrait,
cropped to 2:3 around its most detailed part.
"""

from io import BytesIO

from PIL import Image, ImageFilter

CARD_RATIO = 2 / 3
# Matches the frontend: closer than this to 2:3 fills the card with a small crop.
RATIO_TOLERANCE = 0.15
# Bars count as padding when each covers this much of the side and the two are about equal.
MIN_BAR = 0.08
MAX_BAR_DIFFERENCE = 0.12
SAMPLE_WIDTH = 96
FORMATS = {"JPEG": "JPEG", "PNG": "PNG", "WEBP": "WEBP"}


def _energy(image: Image.Image) -> tuple[list[float], list[float]]:
    """Mean edge strength of each row and each column of a small grayscale sample."""
    width, height = image.size
    sample = image.convert("L").resize((SAMPLE_WIDTH, max(1, round(height * SAMPLE_WIDTH / width))))
    # FIND_EDGES marks the outermost pixels; drop them so a border never reads as detail.
    edges = sample.filter(ImageFilter.FIND_EDGES).crop((1, 1, sample.width - 1, sample.height - 1))
    w, h = edges.size
    pixels = edges.tobytes()
    rows = [sum(pixels[y * w:(y + 1) * w]) / w for y in range(h)]
    columns = [sum(pixels[x::w]) / h for x in range(w)]
    return rows, columns


def _bars(energy: list[float]) -> tuple[int, int]:
    """Leading and trailing low-detail runs, if they look like symmetric padding; else (0, 0)."""
    if not energy:
        return 0, 0
    threshold = max(4.0, 0.2 * sum(energy) / len(energy))
    lead = next((index for index, value in enumerate(energy) if value >= threshold), len(energy))
    trail = next((index for index, value in enumerate(reversed(energy)) if value >= threshold), len(energy))
    size = len(energy)
    if lead + trail >= size:
        return 0, 0
    if lead / size >= MIN_BAR and trail / size >= MIN_BAR and abs(lead - trail) / size <= MAX_BAR_DIFFERENCE:
        return lead, trail
    return 0, 0


def content_box(image: Image.Image) -> tuple[int, int, int, int]:
    """The picture area without letterbox or pillarbox padding, in image pixels."""
    width, height = image.size
    rows, columns = _energy(image)
    scale_y = height / (len(rows) + 2)
    scale_x = width / (len(columns) + 2)
    top, bottom = _bars(rows)
    left, right = _bars(columns)
    return (
        round((left + 1) * scale_x) if left else 0,
        round((top + 1) * scale_y) if top else 0,
        width - round((right + 1) * scale_x) if right else width,
        height - round((bottom + 1) * scale_y) if bottom else height,
    )


def content_ratio(contents: bytes) -> float | None:
    try:
        with Image.open(BytesIO(contents)) as image:
            left, top, right, bottom = content_box(image)
    except Exception:
        return None
    return (right - left) / (bottom - top)


def fits_card(ratio: float | None) -> bool:
    return ratio is not None and abs(ratio - CARD_RATIO) / CARD_RATIO <= RATIO_TOLERANCE


def _best_window(energy: list[float], window: int) -> int:
    """Start of the window with the most detail; ties keep the centre."""
    if window >= len(energy):
        return 0
    centre = (len(energy) - window) // 2
    best, best_score = centre, sum(energy[centre:centre + window])
    for start in range(len(energy) - window + 1):
        score = sum(energy[start:start + window])
        if score > best_score * 1.05:
            best, best_score = start, score
    return best


def fit_cover(contents: bytes) -> bytes | None:
    """A 2:3 crop of off-shape cover art, or None when it already fits the card (or is not a raster image)."""
    try:
        with Image.open(BytesIO(contents)) as image:
            image_format = FORMATS.get(image.format or "")
            if image_format is None:
                return None
            image.load()
            box = content_box(image)
            left, top, right, bottom = box
            ratio = (right - left) / (bottom - top)
            if fits_card(ratio) and box == (0, 0, *image.size):
                return None
            picture = image.crop(box)
            rows, columns = _energy(picture)
            if ratio > CARD_RATIO:
                width = round(picture.height * CARD_RATIO)
                start = _best_window(columns, round(width * len(columns) / picture.width))
                x = min(round(start * picture.width / len(columns)), picture.width - width)
                picture = picture.crop((x, 0, x + width, picture.height))
            else:
                height = round(picture.width / CARD_RATIO)
                start = _best_window(rows, round(height * len(rows) / picture.height))
                y = min(round(start * picture.height / len(rows)), picture.height - height)
                picture = picture.crop((0, y, picture.width, y + height))
            if image_format == "JPEG" and picture.mode not in ("RGB", "L"):
                picture = picture.convert("RGB")
            output = BytesIO()
            picture.save(output, format=image_format, quality=92)
            return output.getvalue()
    except Exception:
        return None
