"""Visual reference generator for high-fidelity look-dev images.

This module provides AI-generated reference images for selected shots,
while keeping the edit/timing/sequencing unchanged. It is invoked only
for shots with fidelity_level=REFERENCE.

The generator is designed as a drop-in alternative to PlaceholderGenerator
with the same interface (generate() method taking AssetRequirement).
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from src.common.logging import get_logger
from src.common.models import Asset, AssetType, ShotVisualSpec, VisualFidelityLevel
from src.common.models.base import generate_id
from src.generation.manifest import AssetRequirement

logger = get_logger(__name__)


# Cost estimates per image (in USD)
REFERENCE_COST_ESTIMATES = {
    "stub": 0.0,  # Stub generator (no API calls)
    "dalle3": 0.04,  # DALL-E 3 standard
    "dalle3_hd": 0.08,  # DALL-E 3 HD
    "midjourney": 0.05,  # Approximate
    "stable_diffusion": 0.01,  # Self-hosted or API
}


class ImageGeneratorBackend(ABC):
    """Abstract base class for image generation backends."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        width: int,
        height: int,
        style_hints: list[str],
        visual_spec: ShotVisualSpec | None = None,
    ) -> tuple[Image.Image, float]:
        """Generate an image from the prompt.

        Returns:
            Tuple of (PIL Image, generation cost in USD)
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend name for logging."""
        pass


class StubReferenceBackend(ImageGeneratorBackend):
    """Stub backend that generates enhanced placeholder-style images.

    This allows testing the pipeline without API costs.
    The images are clearly marked as "REFERENCE STUB" to distinguish
    from actual AI-generated content.
    """

    @property
    def name(self) -> str:
        return "stub_reference"

    async def generate(
        self,
        prompt: str,
        width: int,
        height: int,
        style_hints: list[str],
        visual_spec: ShotVisualSpec | None = None,
    ) -> tuple[Image.Image, float]:
        """Generate a stub reference image with enhanced visual styling."""
        # Create a more sophisticated placeholder than the regular one
        # to visually distinguish REFERENCE from PLACEHOLDER

        # Use visual spec to determine color palette
        if visual_spec and visual_spec.lighting_style:
            from src.generation.placeholder import get_lighting_colors
            colors = get_lighting_colors(visual_spec.lighting_style)
            bg_color = colors["bg"]
            fg_color = colors["fg"]
            accent_color = colors["accent"]
        else:
            bg_color = (30, 35, 45)
            fg_color = (200, 180, 140)
            accent_color = (255, 200, 100)

        # Create image with gradient background
        img = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        # Add vertical gradient for depth
        for y in range(height):
            factor = 1.0 - (y / height) * 0.3
            r = int(bg_color[0] * factor)
            g = int(bg_color[1] * factor)
            b = int(bg_color[2] * factor)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # Draw "REFERENCE" border to clearly mark it
        border_width = 8
        draw.rectangle(
            [(0, 0), (width - 1, height - 1)],
            outline=accent_color,
            width=border_width,
        )

        # Draw inner decorative frame
        margin = 40
        draw.rectangle(
            [(margin, margin), (width - margin, height - margin)],
            outline=fg_color,
            width=2,
        )

        # Draw corner accents
        corner_size = 30
        for x, y in [(margin, margin), (width - margin - corner_size, margin),
                     (margin, height - margin - corner_size),
                     (width - margin - corner_size, height - margin - corner_size)]:
            draw.rectangle(
                [(x, y), (x + corner_size, y + corner_size)],
                outline=accent_color,
                width=2,
            )

        # Add "REFERENCE" label at top
        try:
            font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
            font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
        except (OSError, IOError):
            font_large = ImageFont.load_default()
            font_small = font_large

        # Reference label
        label = "REFERENCE"
        label_bbox = draw.textbbox((0, 0), label, font=font_large)
        label_width = label_bbox[2] - label_bbox[0]
        draw.text(
            ((width - label_width) // 2, margin + 20),
            label,
            fill=accent_color,
            font=font_large,
        )

        # Shot role if available
        if visual_spec:
            role_text = f"[{visual_spec.role.value.upper()}]"
            role_bbox = draw.textbbox((0, 0), role_text, font=font_small)
            role_width = role_bbox[2] - role_bbox[0]
            draw.text(
                ((width - role_width) // 2, margin + 50),
                role_text,
                fill=fg_color,
                font=font_small,
            )

        # Draw prompt summary (truncated)
        prompt_lines = []
        max_chars_per_line = 50
        words = prompt.split()
        current_line = ""
        for word in words[:30]:  # Limit words
            if len(current_line) + len(word) + 1 <= max_chars_per_line:
                current_line = f"{current_line} {word}".strip()
            else:
                if current_line:
                    prompt_lines.append(current_line)
                current_line = word
            if len(prompt_lines) >= 4:
                break
        if current_line and len(prompt_lines) < 4:
            prompt_lines.append(current_line)

        # Draw prompt text
        y_offset = height // 2 - len(prompt_lines) * 10
        for line in prompt_lines:
            line_bbox = draw.textbbox((0, 0), line, font=font_small)
            line_width = line_bbox[2] - line_bbox[0]
            draw.text(
                ((width - line_width) // 2, y_offset),
                line,
                fill=fg_color,
                font=font_small,
            )
            y_offset += 20

        # Add style hints at bottom
        if style_hints:
            hints_text = " | ".join(style_hints[:3])
            hints_bbox = draw.textbbox((0, 0), hints_text, font=font_small)
            hints_width = hints_bbox[2] - hints_bbox[0]
            draw.text(
                ((width - hints_width) // 2, height - margin - 30),
                hints_text,
                fill=fg_color,
                font=font_small,
            )

        # Add subtle noise for texture
        import random
        pixels = img.load()
        for _ in range(width * height // 100):
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)
            noise = random.randint(-10, 10)
            r, g, b = pixels[x, y]
            pixels[x, y] = (
                max(0, min(255, r + noise)),
                max(0, min(255, g + noise)),
                max(0, min(255, b + noise)),
            )

        # Stub has no cost
        return img, REFERENCE_COST_ESTIMATES["stub"]


class VisualReferenceGenerator:
    """Generator for high-fidelity reference images.

    This generator is invoked for shots marked with fidelity_level=REFERENCE.
    It uses a configurable backend for actual image generation.

    Design principles:
    - Same interface as PlaceholderGenerator for drop-in replacement
    - Does NOT change shot timing, count, or sequencing
    - Only affects visual content within the shot
    - Tracks generation cost for budget control
    """

    def __init__(
        self,
        output_dir: str = "outputs/reference_assets",
        backend: ImageGeneratorBackend | None = None,
        cost_cap_usd: float = 1.0,  # Default cost cap per generation run
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Default to stub backend if none provided
        self.backend = backend or StubReferenceBackend()
        self.cost_cap_usd = cost_cap_usd
        self.total_cost_usd = 0.0

    async def generate(self, requirement: AssetRequirement) -> Asset:
        """Generate a reference image for the given requirement.

        Args:
            requirement: Asset requirement from the manifest

        Returns:
            Asset with reference image path and metadata

        Raises:
            ValueError: If cost cap would be exceeded
        """
        start_time = time.time()

        # Only generate images, not audio
        if requirement.asset_type != AssetType.IMAGE:
            raise ValueError(
                f"VisualReferenceGenerator only handles images, got {requirement.asset_type}"
            )

        # Check if we're at the cost cap
        estimated_cost = REFERENCE_COST_ESTIMATES.get(self.backend.name, 0.04)
        if self.total_cost_usd + estimated_cost > self.cost_cap_usd:
            logger.warning(
                "cost_cap_reached",
                total_cost=self.total_cost_usd,
                cap=self.cost_cap_usd,
                shot_id=requirement.shot_id,
            )
            raise ValueError(
                f"Cost cap of ${self.cost_cap_usd:.2f} would be exceeded. "
                f"Current total: ${self.total_cost_usd:.2f}"
            )

        # Build prompt from requirement
        prompt = requirement.prompt or requirement.shot_id
        style_hints = list(requirement.style_hints)

        # Add visual spec hints if available
        visual_spec = requirement.visual_spec
        if visual_spec:
            if visual_spec.lighting_style:
                style_hints.append(visual_spec.lighting_style.value)
            if visual_spec.color_temperature:
                style_hints.append(f"{visual_spec.color_temperature} tones")
            if visual_spec.style_keywords:
                style_hints.extend(visual_spec.style_keywords[:3])

        # Generate image
        logger.info(
            "generating_reference_image",
            shot_id=requirement.shot_id,
            backend=self.backend.name,
            width=requirement.target_width,
            height=requirement.target_height,
        )

        image, generation_cost = await self.backend.generate(
            prompt=prompt,
            width=requirement.target_width,
            height=requirement.target_height,
            style_hints=style_hints,
            visual_spec=visual_spec,
        )

        self.total_cost_usd += generation_cost

        # Generate unique filename
        content_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
        filename = f"{requirement.shot_id}_{content_hash}_ref.png"
        output_path = self.output_dir / filename

        # Save image
        image.save(output_path, "PNG")
        generation_time = time.time() - start_time

        logger.info(
            "reference_image_generated",
            shot_id=requirement.shot_id,
            path=str(output_path),
            cost=generation_cost,
            time=generation_time,
            backend=self.backend.name,
        )

        # Create asset
        asset = Asset(
            id=generate_id("asset"),
            asset_type=AssetType.IMAGE,
            shot_id=requirement.shot_id,
            scene_id=requirement.scene_id,
            file_path=str(output_path),
            file_size_bytes=output_path.stat().st_size,
            generation_model=f"reference_{self.backend.name}",
            generation_prompt=prompt[:500],
            generation_cost=generation_cost,
            generation_time_seconds=generation_time,
            created_at=datetime.utcnow(),
            generation_params={
                "fidelity_level": "reference",
                "backend": self.backend.name,
                "style_hints": style_hints,
                "shot_role": visual_spec.role.value if visual_spec else None,
            },
        )

        return asset

    def reset_cost_tracking(self) -> None:
        """Reset the cost tracker (e.g., between pipeline runs)."""
        self.total_cost_usd = 0.0

    def get_cost_report(self) -> dict:
        """Return cost tracking summary."""
        return {
            "total_cost_usd": self.total_cost_usd,
            "cost_cap_usd": self.cost_cap_usd,
            "remaining_budget_usd": self.cost_cap_usd - self.total_cost_usd,
            "backend": self.backend.name,
        }


# Factory function for creating generators with different backends
def create_reference_generator(
    backend_name: str = "stub",
    output_dir: str = "outputs/reference_assets",
    cost_cap_usd: float = 1.0,
    **backend_kwargs,
) -> VisualReferenceGenerator:
    """Create a reference generator with the specified backend.

    Args:
        backend_name: Name of the backend ("stub", "dalle3", etc.)
        output_dir: Output directory for generated images
        cost_cap_usd: Maximum cost allowed for generation
        **backend_kwargs: Additional kwargs for backend initialization

    Returns:
        Configured VisualReferenceGenerator
    """
    if backend_name == "stub":
        backend = StubReferenceBackend()
    else:
        # Future: Add real backends here
        # elif backend_name == "dalle3":
        #     backend = DallE3Backend(**backend_kwargs)
        logger.warning(
            "unknown_backend_using_stub",
            requested=backend_name,
        )
        backend = StubReferenceBackend()

    return VisualReferenceGenerator(
        output_dir=output_dir,
        backend=backend,
        cost_cap_usd=cost_cap_usd,
    )
