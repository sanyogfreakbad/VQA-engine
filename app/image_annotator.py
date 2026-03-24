"""
Image annotation utilities for marking differences on web screenshots.

Draws red bounding boxes and numbered markers on the web image
to visually indicate where differences were found.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from app.schemas import BoundingBox


# Annotation styling constants
BOX_COLOR = (220, 38, 38)  # Bright red for visibility
BOX_WIDTH = 4
BOX_FILL_ALPHA = 30  # Semi-transparent fill
MARKER_RADIUS = 16
MARKER_COLOR = (220, 38, 38)
MARKER_TEXT_COLOR = (255, 255, 255)
MARKER_FONT_SIZE = 14


def annotate_image(
    web_png: bytes,
    annotations: list[tuple[int, "BoundingBox"]],
) -> bytes:
    """
    Annotate the web image with red bounding boxes and numbered markers.
    
    Args:
        web_png: The web screenshot as PNG bytes
        annotations: List of (diff_id, bounding_box) tuples
        
    Returns:
        Annotated image as PNG bytes
    """
    img = Image.open(io.BytesIO(web_png))
    img = img.convert("RGBA")
    img_width, img_height = img.size
    
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", MARKER_FONT_SIZE)
    except (OSError, IOError):
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", MARKER_FONT_SIZE)
        except (OSError, IOError):
            font = ImageFont.load_default()
    
    for diff_id, bbox in annotations:
        if bbox is None:
            continue
            
        x = int(bbox.x * img_width / 1000)
        y = int(bbox.y * img_height / 1000)
        w = int(bbox.width * img_width / 1000)
        h = int(bbox.height * img_height / 1000)
        
        x = max(0, min(x, img_width - 1))
        y = max(0, min(y, img_height - 1))
        w = max(10, min(w, img_width - x))
        h = max(10, min(h, img_height - y))
        
        _draw_rounded_box(draw, x, y, w, h, BOX_COLOR, BOX_WIDTH)
        _draw_marker(draw, diff_id, x, y, font)
    
    result = Image.alpha_composite(img, overlay)
    result = result.convert("RGB")
    
    buf = io.BytesIO()
    result.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _draw_rounded_box(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    color: tuple[int, int, int],
    width: int,
) -> None:
    """Draw a rectangle with semi-transparent fill and solid border."""
    x1, y1 = x, y
    x2, y2 = x + w, y + h
    
    draw.rectangle(
        [x1, y1, x2, y2],
        fill=color + (BOX_FILL_ALPHA,),
        outline=None,
    )
    
    for i in range(width):
        draw.rectangle(
            [x1 + i, y1 + i, x2 - i, y2 - i],
            outline=color + (255,),
        )


def _draw_marker(
    draw: ImageDraw.ImageDraw,
    diff_id: int,
    x: int,
    y: int,
    font: ImageFont.FreeTypeFont,
) -> None:
    """Draw a numbered circular marker at the top-left of the bounding box."""
    marker_x = x - MARKER_RADIUS // 2
    marker_y = y - MARKER_RADIUS // 2
    
    marker_x = max(MARKER_RADIUS + 2, marker_x)
    marker_y = max(MARKER_RADIUS + 2, marker_y)
    
    draw.ellipse(
        [
            marker_x - MARKER_RADIUS + 2,
            marker_y - MARKER_RADIUS + 2,
            marker_x + MARKER_RADIUS + 2,
            marker_y + MARKER_RADIUS + 2,
        ],
        fill=(0, 0, 0, 100),
    )
    
    draw.ellipse(
        [
            marker_x - MARKER_RADIUS,
            marker_y - MARKER_RADIUS,
            marker_x + MARKER_RADIUS,
            marker_y + MARKER_RADIUS,
        ],
        fill=MARKER_COLOR + (255,),
        outline=(255, 255, 255, 255),
        width=3,
    )
    
    text = str(diff_id)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    text_x = marker_x - text_width // 2
    text_y = marker_y - text_height // 2 - 1
    
    draw.text(
        (text_x, text_y),
        text,
        fill=MARKER_TEXT_COLOR + (255,),
        font=font,
    )
