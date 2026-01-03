"""Placeholder image generator with ShotVisualSpec-driven visual differentiation."""

from __future__ import annotations

import hashlib
import math
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from src.common.logging import get_logger
from src.common.models import Asset, AssetType, ShotVisualSpec, LightingStyle, CompositionZone, ShotRole
from src.common.models.base import generate_id
from src.generation.manifest import AssetRequirement

logger = get_logger(__name__)


# Color palettes based on lighting style (maps ShotVisualSpec lighting to colors)
LIGHTING_COLORS = {
    LightingStyle.NATURAL: {"bg": (50, 55, 60), "fg": (180, 185, 190), "accent": (200, 205, 210), "gradient": "down"},
    LightingStyle.HIGH_KEY: {"bg": (80, 80, 80), "fg": (230, 230, 230), "accent": (255, 255, 200), "gradient": "none"},
    LightingStyle.LOW_KEY: {"bg": (20, 20, 25), "fg": (120, 110, 100), "accent": (180, 80, 60), "gradient": "down"},
    LightingStyle.REMBRANDT: {"bg": (35, 30, 25), "fg": (160, 140, 100), "accent": (220, 180, 100), "gradient": "diagonal"},
    LightingStyle.SILHOUETTE: {"bg": (15, 15, 20), "fg": (40, 40, 45), "accent": (255, 180, 100), "gradient": "up"},
    LightingStyle.GOLDEN_HOUR: {"bg": (60, 45, 30), "fg": (255, 200, 120), "accent": (255, 150, 50), "gradient": "up"},
    LightingStyle.BLUE_HOUR: {"bg": (25, 35, 55), "fg": (100, 140, 200), "accent": (80, 120, 200), "gradient": "down"},
    LightingStyle.DRAMATIC: {"bg": (25, 20, 20), "fg": (200, 80, 60), "accent": (255, 100, 50), "gradient": "diagonal"},
    LightingStyle.DIFFUSED: {"bg": (60, 65, 70), "fg": (200, 200, 200), "accent": (180, 190, 200), "gradient": "none"},
}

# Composition zone to screen position mapping
ZONE_POSITIONS = {
    CompositionZone.CENTER: (0.5, 0.5),
    CompositionZone.TOP_LEFT: (0.25, 0.25),
    CompositionZone.TOP_CENTER: (0.5, 0.25),
    CompositionZone.TOP_RIGHT: (0.75, 0.25),
    CompositionZone.MIDDLE_LEFT: (0.25, 0.5),
    CompositionZone.MIDDLE_RIGHT: (0.75, 0.5),
    CompositionZone.BOTTOM_LEFT: (0.25, 0.75),
    CompositionZone.BOTTOM_CENTER: (0.5, 0.75),
    CompositionZone.BOTTOM_RIGHT: (0.75, 0.75),
    CompositionZone.FULL_FRAME: (0.5, 0.5),
}

# Role-specific visual indicators
ROLE_INDICATORS = {
    ShotRole.ESTABLISHING: {"shape": "horizon", "label": "ESTABLISHING", "weight": "bold"},
    ShotRole.ACTION: {"shape": "dynamic", "label": "ACTION", "weight": "bold"},
    ShotRole.REACTION: {"shape": "focus", "label": "REACTION", "weight": "medium"},
    ShotRole.DETAIL: {"shape": "macro", "label": "DETAIL", "weight": "thin"},
    ShotRole.TRANSITION: {"shape": "bridge", "label": "TRANSITION", "weight": "medium"},
    ShotRole.MONTAGE: {"shape": "grid", "label": "MONTAGE", "weight": "thin"},
    ShotRole.CLIMAX: {"shape": "burst", "label": "CLIMAX", "weight": "bold"},
    ShotRole.RESOLUTION: {"shape": "fade", "label": "RESOLUTION", "weight": "thin"},
}

# Legacy mood colors for backward compatibility
MOOD_COLORS = {
    "tension": {"bg": (40, 30, 30), "fg": (200, 100, 100), "accent": (255, 80, 80)},
    "sorrow": {"bg": (30, 35, 45), "fg": (100, 120, 160), "accent": (80, 100, 200)},
    "hope": {"bg": (45, 45, 35), "fg": (180, 180, 120), "accent": (255, 220, 100)},
    "triumph": {"bg": (45, 40, 25), "fg": (200, 170, 100), "accent": (255, 200, 50)},
    "contemplative": {"bg": (35, 40, 45), "fg": (140, 150, 170), "accent": (150, 180, 200)},
    "action": {"bg": (35, 25, 25), "fg": (180, 100, 80), "accent": (255, 120, 50)},
    "mystery": {"bg": (25, 25, 35), "fg": (100, 100, 150), "accent": (150, 100, 200)},
    "neutral": {"bg": (40, 40, 40), "fg": (150, 150, 150), "accent": (180, 180, 180)},
}


def get_mood_colors(mood: str) -> dict:
    """Get colors for a mood."""
    mood_key = mood.lower() if mood else "neutral"
    return MOOD_COLORS.get(mood_key, MOOD_COLORS["neutral"])


def get_lighting_colors(lighting_style: LightingStyle | None) -> dict:
    """Get colors for a lighting style."""
    if lighting_style is None:
        return LIGHTING_COLORS[LightingStyle.NATURAL]
    return LIGHTING_COLORS.get(lighting_style, LIGHTING_COLORS[LightingStyle.NATURAL])


def _draw_gradient(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    bg_color: tuple[int, int, int],
    gradient_type: str,
) -> None:
    """Draw a gradient background based on lighting style."""
    if gradient_type == "none":
        return  # Solid color already set

    for y in range(height):
        for x in range(width):
            if gradient_type == "down":
                factor = y / height
            elif gradient_type == "up":
                factor = 1 - (y / height)
            elif gradient_type == "diagonal":
                factor = (x + y) / (width + height)
            else:
                factor = 0

            # Apply gradient darkening
            factor = factor * 0.4  # Max 40% darkening
            r = int(bg_color[0] * (1 - factor))
            g = int(bg_color[1] * (1 - factor))
            b = int(bg_color[2] * (1 - factor))
            draw.point((x, y), fill=(r, g, b))


def _draw_role_indicator(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    role: ShotRole,
    colors: dict,
) -> None:
    """Draw role-specific visual elements."""
    indicator = ROLE_INDICATORS.get(role, ROLE_INDICATORS[ShotRole.ACTION])
    shape = indicator["shape"]
    weight = indicator["weight"]

    line_width = {"thin": 1, "medium": 2, "bold": 3}.get(weight, 2)
    fg = colors["fg"]

    if shape == "horizon":
        # Wide horizontal lines for establishing
        for i in range(3):
            y = height // 4 + i * (height // 4)
            draw.line([(50, y), (width - 50, y)], fill=fg, width=line_width)

    elif shape == "dynamic":
        # Diagonal action lines
        for i in range(5):
            x_offset = i * (width // 4)
            draw.line([(x_offset, 0), (x_offset + 200, height)], fill=fg, width=line_width)

    elif shape == "focus":
        # Concentric circles for reaction/attention
        cx, cy = width // 2, height // 2
        for r in [80, 160, 240]:
            draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], outline=fg, width=line_width)

    elif shape == "macro":
        # Tight framing lines for detail shots
        margin = min(100, width // 8, height // 8)
        if margin > 10:
            draw.rectangle(
                [(margin, margin), (width - margin, height - margin)],
                outline=fg, width=line_width * 2
            )
            # Inner frame
            inner_margin = margin * 2
            if inner_margin < width // 2 and inner_margin < height // 2:
                draw.rectangle(
                    [(inner_margin, inner_margin), (width - inner_margin, height - inner_margin)],
                    outline=fg, width=line_width
                )

    elif shape == "bridge":
        # Flowing curves for transitions
        for i in range(3):
            y_offset = (i - 1) * 100
            points = [(0, height // 2 + y_offset)]
            for x in range(0, width + 1, 50):
                y = height // 2 + y_offset + int(50 * math.sin(x * math.pi / 300))
                points.append((x, y))
            draw.line(points, fill=fg, width=line_width)

    elif shape == "grid":
        # Montage grid pattern
        for i in range(1, 4):
            x = width * i // 4
            draw.line([(x, 50), (x, height - 50)], fill=fg, width=line_width)
        for i in range(1, 4):
            y = height * i // 4
            draw.line([(50, y), (width - 50, y)], fill=fg, width=line_width)

    elif shape == "burst":
        # Radiating lines for climax
        cx, cy = width // 2, height // 2
        for angle in range(0, 360, 30):
            rad = math.radians(angle)
            x2 = cx + int(400 * math.cos(rad))
            y2 = cy + int(400 * math.sin(rad))
            draw.line([(cx, cy), (x2, y2)], fill=fg, width=line_width)

    elif shape == "fade":
        # Gentle horizontal fade lines for resolution
        for i in range(5):
            y = height // 6 + i * (height // 6)
            alpha = 1 - (i / 5)
            line_color = tuple(int(c * alpha) for c in fg)
            draw.line([(100, y), (width - 100, y)], fill=line_color, width=line_width)


def _draw_composition_zone(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    zone: CompositionZone,
    colors: dict,
) -> None:
    """Draw composition zone indicator."""
    pos = ZONE_POSITIONS.get(zone, (0.5, 0.5))
    cx = int(width * pos[0])
    cy = int(height * pos[1])

    # Draw zone indicator (crosshair at composition point)
    size = 40
    accent = colors["accent"]

    # Crosshair
    draw.line([(cx - size, cy), (cx + size, cy)], fill=accent, width=2)
    draw.line([(cx, cy - size), (cx, cy + size)], fill=accent, width=2)

    # Zone circle
    draw.ellipse([(cx - 60, cy - 60), (cx + 60, cy + 60)], outline=accent, width=1)


def create_placeholder_with_visual_spec(
    width: int = 1920,
    height: int = 1080,
    visual_spec: ShotVisualSpec | None = None,
    text: str = "Placeholder",
    shot_type: str = "medium",
    output_path: str | None = None,
) -> Image.Image:
    """Create a placeholder image driven by ShotVisualSpec for visual differentiation.

    Different ShotVisualSpecs produce visually distinct images through:
    - Lighting style -> color palette and gradient direction
    - Shot role -> visual indicators (lines, shapes, patterns)
    - Composition zone -> subject placement indicator
    - Symbolism -> text overlays
    """
    # Get colors based on visual spec lighting or fall back to shot_type
    if visual_spec is not None:
        colors = get_lighting_colors(visual_spec.lighting_style)
        role = visual_spec.role
        zone = visual_spec.primary_zone
    else:
        colors = LIGHTING_COLORS[LightingStyle.NATURAL]
        role = ShotRole.ACTION
        zone = CompositionZone.CENTER

    # Create base image
    img = Image.new("RGB", (width, height), colors["bg"])
    draw = ImageDraw.Draw(img)

    # Draw gradient background
    gradient_type = colors.get("gradient", "down")
    if gradient_type != "none":
        # Simplified gradient (line-by-line for performance)
        for y in range(height):
            if gradient_type == "down":
                factor = y / height * 0.4
            elif gradient_type == "up":
                factor = (1 - y / height) * 0.4
            elif gradient_type == "diagonal":
                factor = ((y / height) * 0.3)
            else:
                factor = 0

            r = int(colors["bg"][0] * (1 - factor))
            g = int(colors["bg"][1] * (1 - factor))
            b = int(colors["bg"][2] * (1 - factor))
            draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Draw role-specific visual indicator
    _draw_role_indicator(draw, width, height, role, colors)

    # Draw composition zone indicator
    _draw_composition_zone(draw, width, height, zone, colors)

    # Draw border with accent color
    draw.rectangle([(0, 0), (width - 1, height - 1)], outline=colors["accent"], width=3)

    # Load fonts
    try:
        font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 42)
        font_medium = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
    except (IOError, OSError):
        font_large = ImageFont.load_default()
        font_medium = font_large
        font_small = font_large

    # Draw role badge (top left)
    indicator = ROLE_INDICATORS.get(role, ROLE_INDICATORS[ShotRole.ACTION])
    role_text = indicator["label"]
    badge_width = len(role_text) * 22 + 20
    draw.rectangle([(15, 15), (badge_width, 60)], fill=colors["accent"])
    draw.text((25, 22), role_text, fill=(0, 0, 0), font=font_medium)

    # Draw shot type badge (top right)
    shot_badge = shot_type.upper().replace("_", " ")
    badge_x = width - len(shot_badge) * 18 - 30
    draw.rectangle([(badge_x, 15), (width - 15, 60)], fill=colors["fg"])
    draw.text((badge_x + 10, 22), shot_badge, fill=colors["bg"], font=font_medium)

    # Draw lighting style indicator (bottom left)
    if visual_spec is not None:
        lighting_text = f"Lighting: {visual_spec.lighting_style.value.replace('_', ' ').title()}"
        draw.text((20, height - 80), lighting_text, fill=colors["accent"], font=font_small)

        # Draw camera height (bottom left, below lighting)
        height_text = f"Camera: {visual_spec.camera_height.replace('_', ' ').title()}"
        draw.text((20, height - 55), height_text, fill=colors["fg"], font=font_small)

        # Draw lens type
        lens_text = f"Lens: {visual_spec.lens_type.value.replace('_', ' ').title()}"
        draw.text((20, height - 30), lens_text, fill=colors["fg"], font=font_small)

    # Draw symbolism (bottom right if present)
    if visual_spec is not None and visual_spec.symbols:
        symbol = visual_spec.symbols[0]
        symbol_text = f"Symbol: {symbol.symbol}"
        text_bbox = draw.textbbox((0, 0), symbol_text, font=font_small)
        text_width = text_bbox[2] - text_bbox[0]
        draw.text((width - text_width - 20, height - 55), symbol_text, fill=colors["accent"], font=font_small)

        meaning_text = f"Meaning: {symbol.meaning}"
        text_bbox = draw.textbbox((0, 0), meaning_text, font=font_small)
        text_width = text_bbox[2] - text_bbox[0]
        draw.text((width - text_width - 20, height - 30), meaning_text, fill=colors["fg"], font=font_small)

    # Draw main description text (centered)
    max_width = width - 200
    wrapped_text = _wrap_text(text, font_medium, max_width, draw)

    text_y = height // 2 - (len(wrapped_text) * 35) // 2
    for line in wrapped_text:
        bbox = draw.textbbox((0, 0), line, font=font_medium)
        text_width = bbox[2] - bbox[0]
        text_x = (width - text_width) // 2
        # Draw text shadow
        draw.text((text_x + 2, text_y + 2), line, fill=(0, 0, 0), font=font_medium)
        draw.text((text_x, text_y), line, fill=colors["fg"], font=font_medium)
        text_y += 40

    # Draw reference films (top center) if available
    if visual_spec is not None and visual_spec.reference_films:
        ref_text = f"Style: {', '.join(visual_spec.reference_films[:2])}"
        text_bbox = draw.textbbox((0, 0), ref_text, font=font_small)
        text_width = text_bbox[2] - text_bbox[0]
        draw.text(((width - text_width) // 2, 70), ref_text, fill=colors["fg"], font=font_small)

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, "PNG")
        logger.debug("placeholder_saved", path=output_path)

    return img


def create_placeholder_image(
    width: int = 1920,
    height: int = 1080,
    text: str = "Placeholder",
    mood: str = "neutral",
    shot_type: str = "medium",
    output_path: str | None = None,
) -> Image.Image:
    """Create a placeholder image with visual styling."""

    colors = get_mood_colors(mood)

    # Create base image with gradient
    img = Image.new("RGB", (width, height), colors["bg"])
    draw = ImageDraw.Draw(img)

    # Draw gradient effect
    for y in range(height):
        factor = y / height
        r = int(colors["bg"][0] * (1 - factor * 0.3))
        g = int(colors["bg"][1] * (1 - factor * 0.3))
        b = int(colors["bg"][2] * (1 - factor * 0.3))
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Draw composition guides based on shot type
    guide_color = (*colors["fg"], 100)  # Semi-transparent

    if shot_type in ["extreme_wide", "wide"]:
        # Thirds grid for wide shots
        for i in [1, 2]:
            x = width * i // 3
            y = height * i // 3
            draw.line([(x, 0), (x, height)], fill=colors["fg"], width=1)
            draw.line([(0, y), (width, y)], fill=colors["fg"], width=1)
    elif shot_type in ["close_up", "extreme_close"]:
        # Center focus for close shots
        cx, cy = width // 2, height // 2
        for r in [100, 200, 300]:
            draw.ellipse(
                [(cx - r, cy - r), (cx + r, cy + r)],
                outline=colors["fg"],
                width=1,
            )
    else:
        # Rule of thirds for medium shots
        for i in [1, 2]:
            x = width * i // 3
            y = height * i // 3
            draw.line([(x, 0), (x, height)], fill=colors["fg"], width=1)
            draw.line([(0, y), (width, y)], fill=colors["fg"], width=1)

    # Draw border
    draw.rectangle([(0, 0), (width - 1, height - 1)], outline=colors["accent"], width=2)

    # Draw shot type indicator
    try:
        font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
    except (IOError, OSError):
        font_large = ImageFont.load_default()
        font_small = font_large

    # Shot type badge
    badge_text = shot_type.upper().replace("_", " ")
    draw.rectangle([(20, 20), (20 + len(badge_text) * 25, 70)], fill=colors["accent"])
    draw.text((30, 30), badge_text, fill=(0, 0, 0), font=font_large)

    # Main text (description)
    max_width = width - 100
    wrapped_text = _wrap_text(text, font_small, max_width, draw)

    text_y = height // 2 - (len(wrapped_text) * 30) // 2
    for line in wrapped_text:
        bbox = draw.textbbox((0, 0), line, font=font_small)
        text_width = bbox[2] - bbox[0]
        text_x = (width - text_width) // 2
        draw.text((text_x, text_y), line, fill=colors["fg"], font=font_small)
        text_y += 35

    # Mood indicator at bottom
    mood_text = f"Mood: {mood.capitalize()}"
    draw.text((20, height - 50), mood_text, fill=colors["accent"], font=font_small)

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, "PNG")
        logger.debug("placeholder_saved", path=output_path)

    return img


def _wrap_text(text: str, font, max_width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    """Wrap text to fit within max_width."""
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]

    if current_line:
        lines.append(" ".join(current_line))

    return lines[:5]  # Max 5 lines


class PlaceholderGenerator:
    """Generator for placeholder images."""

    def __init__(self, output_dir: str = "outputs/assets"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def generate(self, requirement: AssetRequirement) -> Asset:
        """Generate a placeholder image for a requirement.

        Uses ShotVisualSpec when available for visually differentiated placeholders.
        Different shots will have distinct colors, patterns, and indicators.
        """
        start_time = time.time()

        # Get shot type from requirement or parse from prompt
        shot_type = requirement.shot_type if requirement.shot_type else "medium"
        if shot_type == "medium":
            for st in ["extreme_wide", "wide", "medium_wide", "medium", "close_up", "extreme_close"]:
                if st in requirement.prompt.lower():
                    shot_type = st
                    break

        # Generate unique filename
        content_hash = hashlib.md5(
            f"{requirement.shot_id}:{requirement.prompt}".encode()
        ).hexdigest()[:8]
        filename = f"{requirement.shot_id}_{content_hash}.png"
        output_path = self.output_dir / filename

        # Create image using visual_spec if available (visually differentiated)
        if requirement.visual_spec is not None:
            img = create_placeholder_with_visual_spec(
                width=requirement.target_width,
                height=requirement.target_height,
                visual_spec=requirement.visual_spec,
                text=requirement.prompt[:200],
                shot_type=shot_type,
                output_path=str(output_path),
            )
            generation_model = "placeholder_generator_v2_visual_spec"
            quality_notes = [
                "Visually differentiated placeholder",
                f"Role: {requirement.visual_spec.role.value}",
                f"Lighting: {requirement.visual_spec.lighting_style.value}",
            ]
        else:
            # Fallback to legacy generation
            mood = requirement.style_hints[0] if requirement.style_hints else "neutral"
            img = create_placeholder_image(
                width=requirement.target_width,
                height=requirement.target_height,
                text=requirement.prompt[:200],
                mood=mood,
                shot_type=shot_type,
                output_path=str(output_path),
            )
            generation_model = "placeholder_generator_v1"
            quality_notes = ["Legacy placeholder - no visual spec"]

        generation_time = time.time() - start_time
        file_size = output_path.stat().st_size

        # Build generation params
        gen_params = {
            "width": requirement.target_width,
            "height": requirement.target_height,
            "shot_type": shot_type,
        }
        if requirement.visual_spec is not None:
            gen_params["role"] = requirement.visual_spec.role.value
            gen_params["lighting_style"] = requirement.visual_spec.lighting_style.value
            gen_params["composition_zone"] = requirement.visual_spec.primary_zone.value

        asset = Asset(
            asset_type=AssetType.IMAGE,
            shot_id=requirement.shot_id,
            scene_id=requirement.scene_id,
            file_path=str(output_path),
            file_size_bytes=file_size,
            mime_type="image/png",
            checksum=content_hash,
            generation_model=generation_model,
            generation_params=gen_params,
            generation_prompt=requirement.prompt,
            generation_time_seconds=generation_time,
            generation_cost=0.0,
            quality_score=0.6 if requirement.visual_spec else 0.5,
            quality_notes=quality_notes,
        )

        logger.info(
            "placeholder_generated",
            shot_id=requirement.shot_id,
            path=str(output_path),
            size_kb=file_size // 1024,
            has_visual_spec=requirement.visual_spec is not None,
        )

        return asset

    async def generate_all(
        self,
        requirements: list[AssetRequirement],
    ) -> list[Asset]:
        """Generate placeholder images for multiple requirements."""
        assets = []
        for req in requirements:
            if req.asset_type == AssetType.IMAGE:
                asset = await self.generate(req)
                assets.append(asset)
        return assets
