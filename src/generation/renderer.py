"""Minimal MP4 renderer with Ken Burns effect."""

from __future__ import annotations

import asyncio
import subprocess
import tempfile
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from src.common.logging import get_logger
from src.common.models import Shot, CameraMotion, ShotVisualSpec, CompositionZone, Scene
from src.common.models.base import generate_id
from src.generation.manifest import AssetManifest, AssetType
from src.generation.audio_generator import AudioBedGenerator

logger = get_logger(__name__)


class RenderQuality(str, Enum):
    """Render quality presets for video generation.

    DRAFT: Fast iteration with all placeholders, lower quality encoding.
           Best for quick edit checks and internal reviews.

    FOUNDER_PREVIEW: Mixed fidelity with high-quality key shots (3-5).
                     Suitable for founder review and feedback collection.
                     This is the default for pilot runs.

    DEMO_ONLY: All high-fidelity shots (cost-capped at $1.00).
               For demos and presentations only. NOT for iterative feedback.
    """

    DRAFT = "draft"
    FOUNDER_PREVIEW = "founder_preview"
    DEMO_ONLY = "demo_only"


# Render quality presets - maps quality level to config overrides
RENDER_QUALITY_PRESETS = {
    RenderQuality.DRAFT: {
        "crf": 28,  # Lower quality for speed
        "preset": "fast",
        "enable_music_bed": False,
        "reference_backend": "stub",
        "max_reference_shots": 0,  # All placeholders
    },
    RenderQuality.FOUNDER_PREVIEW: {
        "crf": 23,  # Good quality
        "preset": "medium",
        "enable_music_bed": True,
        "reference_backend": "dalle3",  # Real images for key shots
        "max_reference_shots": 5,
        "reference_cost_cap": 0.50,
    },
    RenderQuality.DEMO_ONLY: {
        "crf": 18,  # High quality
        "preset": "slow",
        "enable_music_bed": True,
        "reference_backend": "dalle3",
        "max_reference_shots": 15,  # All shots can be high-fidelity
        "reference_cost_cap": 1.00,
    },
}


class KenBurnsDirection(str, Enum):
    """Direction for Ken Burns effect."""

    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    PAN_LEFT = "pan_left"
    PAN_RIGHT = "pan_right"
    PAN_UP = "pan_up"
    PAN_DOWN = "pan_down"
    STATIC = "static"


@dataclass
class KenBurnsParams:
    """Parameters for Ken Burns effect."""

    direction: KenBurnsDirection
    start_scale: float = 1.0
    end_scale: float = 1.2
    start_x_offset: float = 0.0
    end_x_offset: float = 0.0
    start_y_offset: float = 0.0
    end_y_offset: float = 0.0


def motion_to_ken_burns(motion: CameraMotion | None) -> KenBurnsParams:
    """Convert camera motion spec to Ken Burns parameters."""
    if motion is None:
        return KenBurnsParams(direction=KenBurnsDirection.ZOOM_IN)

    mapping = {
        CameraMotion.STATIC: KenBurnsParams(
            direction=KenBurnsDirection.STATIC,
            start_scale=1.0,
            end_scale=1.0,
        ),
        CameraMotion.PAN_LEFT: KenBurnsParams(
            direction=KenBurnsDirection.PAN_LEFT,
            start_x_offset=0.1,
            end_x_offset=-0.1,
        ),
        CameraMotion.PAN_RIGHT: KenBurnsParams(
            direction=KenBurnsDirection.PAN_RIGHT,
            start_x_offset=-0.1,
            end_x_offset=0.1,
        ),
        CameraMotion.TILT_UP: KenBurnsParams(
            direction=KenBurnsDirection.PAN_UP,
            start_y_offset=0.1,
            end_y_offset=-0.1,
        ),
        CameraMotion.TILT_DOWN: KenBurnsParams(
            direction=KenBurnsDirection.PAN_DOWN,
            start_y_offset=-0.1,
            end_y_offset=0.1,
        ),
        CameraMotion.ZOOM_IN: KenBurnsParams(
            direction=KenBurnsDirection.ZOOM_IN,
            start_scale=1.0,
            end_scale=1.3,
        ),
        CameraMotion.ZOOM_OUT: KenBurnsParams(
            direction=KenBurnsDirection.ZOOM_OUT,
            start_scale=1.3,
            end_scale=1.0,
        ),
        CameraMotion.DOLLY_IN: KenBurnsParams(
            direction=KenBurnsDirection.ZOOM_IN,
            start_scale=1.0,
            end_scale=1.2,
        ),
        CameraMotion.DOLLY_OUT: KenBurnsParams(
            direction=KenBurnsDirection.ZOOM_OUT,
            start_scale=1.2,
            end_scale=1.0,
        ),
        CameraMotion.TRACK_LEFT: KenBurnsParams(
            direction=KenBurnsDirection.PAN_LEFT,
            start_x_offset=0.15,
            end_x_offset=-0.15,
            start_scale=1.1,
            end_scale=1.1,
        ),
        CameraMotion.TRACK_RIGHT: KenBurnsParams(
            direction=KenBurnsDirection.PAN_RIGHT,
            start_x_offset=-0.15,
            end_x_offset=0.15,
            start_scale=1.1,
            end_scale=1.1,
        ),
    }

    return mapping.get(motion, KenBurnsParams(direction=KenBurnsDirection.ZOOM_IN))


def visual_spec_to_ken_burns(visual_spec: ShotVisualSpec) -> KenBurnsParams:
    """Convert ShotVisualSpec to Ken Burns parameters.

    Uses the explicit ken_burns_start_zone, ken_burns_end_zone, and zoom_direction
    from the visual spec for more precise control.
    """
    # Map composition zones to x/y offsets
    zone_offsets = {
        CompositionZone.CENTER: (0.0, 0.0),
        CompositionZone.TOP_LEFT: (-0.15, -0.15),
        CompositionZone.TOP_CENTER: (0.0, -0.15),
        CompositionZone.TOP_RIGHT: (0.15, -0.15),
        CompositionZone.MIDDLE_LEFT: (-0.15, 0.0),
        CompositionZone.MIDDLE_RIGHT: (0.15, 0.0),
        CompositionZone.BOTTOM_LEFT: (-0.15, 0.15),
        CompositionZone.BOTTOM_CENTER: (0.0, 0.15),
        CompositionZone.BOTTOM_RIGHT: (0.15, 0.15),
        CompositionZone.FULL_FRAME: (0.0, 0.0),
    }

    start_x, start_y = zone_offsets.get(visual_spec.ken_burns_start_zone, (0.0, 0.0))
    end_x, end_y = zone_offsets.get(visual_spec.ken_burns_end_zone, (0.0, 0.0))

    # Determine zoom based on zoom_direction
    if visual_spec.zoom_direction == "in":
        start_scale = 1.0
        end_scale = 1.3
        direction = KenBurnsDirection.ZOOM_IN
    elif visual_spec.zoom_direction == "out":
        start_scale = 1.3
        end_scale = 1.0
        direction = KenBurnsDirection.ZOOM_OUT
    else:
        # No zoom, check for pan based on zone difference
        start_scale = 1.1  # Slight scale for pan effect
        end_scale = 1.1
        if start_x != end_x:
            direction = KenBurnsDirection.PAN_RIGHT if end_x > start_x else KenBurnsDirection.PAN_LEFT
        elif start_y != end_y:
            direction = KenBurnsDirection.PAN_DOWN if end_y > start_y else KenBurnsDirection.PAN_UP
        else:
            direction = KenBurnsDirection.STATIC
            start_scale = 1.0
            end_scale = 1.0

    return KenBurnsParams(
        direction=direction,
        start_scale=start_scale,
        end_scale=end_scale,
        start_x_offset=start_x,
        end_x_offset=end_x,
        start_y_offset=start_y,
        end_y_offset=end_y,
    )


class RenderConfig(BaseModel):
    """Configuration for video rendering."""

    output_width: int = 1920
    output_height: int = 1080
    fps: int = 30
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    video_bitrate: str = "5M"
    audio_bitrate: str = "192k"
    preset: str = "medium"
    crf: int = 23  # Quality (lower = better, 18-28 is typical)

    # Ken Burns settings
    default_ken_burns_intensity: float = 1.0
    enable_transitions: bool = True
    transition_duration: float = 0.5

    # Audio settings
    enable_music_bed: bool = True
    music_bed_volume: float = 0.5  # Relative to main audio


def create_render_config(
    quality: RenderQuality = RenderQuality.FOUNDER_PREVIEW,
    **overrides,
) -> RenderConfig:
    """Create a RenderConfig from a quality preset with optional overrides.

    Args:
        quality: The render quality preset to use
        **overrides: Additional config overrides

    Returns:
        Configured RenderConfig
    """
    preset = RENDER_QUALITY_PRESETS.get(quality, {})

    # Extract only RenderConfig-relevant fields from preset
    config_fields = {
        k: v for k, v in preset.items()
        if k in RenderConfig.model_fields
    }

    # Apply overrides
    config_fields.update(overrides)

    return RenderConfig(**config_fields)


def get_quality_preset(quality: RenderQuality) -> dict:
    """Get the full preset configuration for a quality level.

    This includes asset generator settings (backend, cost cap) that
    aren't part of RenderConfig.
    """
    return RENDER_QUALITY_PRESETS.get(quality, RENDER_QUALITY_PRESETS[RenderQuality.FOUNDER_PREVIEW])


class ShotRenderReport(BaseModel):
    """Render report for a single shot."""

    shot_id: str
    sequence: int
    planned_duration: float
    rendered_duration: float
    duration_delta: float  # rendered - planned
    fidelity_level: str = "placeholder"  # "placeholder" or "reference"
    ffmpeg_command: str = ""
    exit_code: int = 0
    stderr: str = ""


class RenderReport(BaseModel):
    """Complete render report for debugging and verification."""

    video_id: str = ""
    story_id: str = ""
    render_timestamp: str = ""
    total_planned_duration: float = 0.0
    total_rendered_duration: float = 0.0
    duration_drift: float = 0.0  # Total drift from planned
    shots: list[ShotRenderReport] = Field(default_factory=list)
    ffmpeg_version: str = ""
    render_config: dict = Field(default_factory=dict)
    success: bool = True
    errors: list[str] = Field(default_factory=list)
    audio_included: bool = False
    audio_path: str | None = None


class RenderResult(BaseModel):
    """Result of rendering operation."""

    success: bool
    output_path: str | None = None
    duration_seconds: float = 0.0
    file_size_bytes: int = 0
    render_time_seconds: float = 0.0
    shots_rendered: int = 0
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    # Detailed report
    render_report: RenderReport | None = None


class VideoRenderer:
    """Minimal video renderer using FFmpeg."""

    def __init__(
        self,
        config: RenderConfig | None = None,
        output_dir: str = "outputs/videos",
    ):
        self.config = config or RenderConfig()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Check FFmpeg availability
        self._ffmpeg_available = self._check_ffmpeg()

    def _check_ffmpeg(self) -> bool:
        """Check if FFmpeg is available."""
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            logger.warning("ffmpeg_not_found")
            return False

    def _generate_ken_burns_filter(
        self,
        params: KenBurnsParams,
        duration: float,
        input_w: int,
        input_h: int,
    ) -> str:
        """Generate FFmpeg filter for Ken Burns effect."""
        out_w = self.config.output_width
        out_h = self.config.output_height

        # Calculate zoom and pan expressions
        # t is time in seconds, d is duration
        if params.direction == KenBurnsDirection.STATIC:
            zoom_expr = f"{params.start_scale}"
            x_expr = f"(iw-iw/{params.start_scale})/2"
            y_expr = f"(ih-ih/{params.start_scale})/2"
        else:
            # Linear interpolation over time
            scale_diff = params.end_scale - params.start_scale
            zoom_expr = f"{params.start_scale}+{scale_diff}*(t/{duration})"

            # Pan calculations
            x_start = params.start_x_offset
            x_end = params.end_x_offset
            x_diff = x_end - x_start
            x_expr = f"(iw-iw/zoom)/2+iw*({x_start}+{x_diff}*(t/{duration}))"

            y_start = params.start_y_offset
            y_end = params.end_y_offset
            y_diff = y_end - y_start
            y_expr = f"(ih-ih/zoom)/2+ih*({y_start}+{y_diff}*(t/{duration}))"

        # Zoompan filter with smooth motion
        filter_str = (
            f"zoompan=z='{zoom_expr}':"
            f"x='{x_expr}':"
            f"y='{y_expr}':"
            f"d={int(duration * self.config.fps)}:"
            f"s={out_w}x{out_h}:"
            f"fps={self.config.fps}"
        )

        return filter_str

    async def render_shot(
        self,
        shot: Shot,
        image_path: str,
        output_path: str,
    ) -> tuple[RenderResult, ShotRenderReport]:
        """Render a single shot with Ken Burns effect. Returns (result, report)."""
        start_time = time.time()

        # Determine fidelity level from visual_spec
        fidelity = "placeholder"
        if shot.visual_spec:
            fidelity = shot.visual_spec.fidelity_level.value

        # Initialize report
        report = ShotRenderReport(
            shot_id=shot.id,
            sequence=shot.sequence,
            planned_duration=shot.duration_seconds,
            rendered_duration=0.0,
            duration_delta=0.0,
            fidelity_level=fidelity,
        )

        if not self._ffmpeg_available:
            report.stderr = "FFmpeg not available"
            report.exit_code = -1
            return RenderResult(success=False, errors=["FFmpeg not available"]), report

        if not Path(image_path).exists():
            report.stderr = f"Image not found: {image_path}"
            report.exit_code = -1
            return RenderResult(success=False, errors=[f"Image not found: {image_path}"]), report

        # Get Ken Burns parameters - prefer visual_spec if available
        if shot.visual_spec is not None:
            kb_params = visual_spec_to_ken_burns(shot.visual_spec)
            logger.debug(
                "using_visual_spec_for_ken_burns",
                shot_id=shot.id,
                role=shot.visual_spec.role.value,
                zoom_dir=shot.visual_spec.zoom_direction,
            )
        else:
            kb_params = motion_to_ken_burns(
                shot.motion.camera_motion if shot.motion else None
            )

        # Generate filter
        filter_str = self._generate_ken_burns_filter(
            kb_params,
            shot.duration_seconds,
            self.config.output_width,
            self.config.output_height,
        )

        # Build FFmpeg command
        cmd = [
            "ffmpeg",
            "-y",
            "-loop", "1",
            "-i", image_path,
            "-vf", filter_str,
            "-t", str(shot.duration_seconds),
            "-c:v", self.config.video_codec,
            "-preset", self.config.preset,
            "-crf", str(self.config.crf),
            "-pix_fmt", "yuv420p",
            output_path,
        ]

        report.ffmpeg_command = " ".join(cmd)
        logger.debug("ffmpeg_command", cmd=report.ffmpeg_command)

        try:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            report.exit_code = result.returncode
            report.stderr = stderr.decode()[:500] if stderr else ""

            if result.returncode != 0:
                return RenderResult(
                    success=False,
                    errors=[f"FFmpeg failed: {report.stderr}"],
                ), report

            output_file = Path(output_path)
            render_time = time.time() - start_time

            # Get actual duration using ffprobe
            actual_duration = await self._get_video_duration(output_path)
            report.rendered_duration = actual_duration
            report.duration_delta = actual_duration - shot.duration_seconds

            return RenderResult(
                success=True,
                output_path=output_path,
                duration_seconds=actual_duration,
                file_size_bytes=output_file.stat().st_size,
                render_time_seconds=render_time,
                shots_rendered=1,
            ), report

        except Exception as e:
            report.stderr = str(e)
            report.exit_code = -1
            return RenderResult(success=False, errors=[str(e)]), report

    async def _get_video_duration(self, video_path: str) -> float:
        """Get actual duration of a video file using ffprobe."""
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path,
            ]
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()
            return float(stdout.decode().strip())
        except Exception:
            return 0.0

    async def render_video(
        self,
        shots: list[Shot],
        manifest: AssetManifest,
        output_filename: str | None = None,
        scenes: list[Scene] | None = None,
    ) -> RenderResult:
        """Render a complete video from shots and assets.

        Args:
            shots: List of shots to render
            manifest: Asset manifest with image assets
            output_filename: Optional output filename
            scenes: Optional list of scenes for music bed mood detection
        """
        from datetime import datetime

        start_time = time.time()
        errors = []
        warnings = []

        # Initialize render report
        video_id = generate_id("video")[:8]
        render_report = RenderReport(
            video_id=video_id,
            story_id=manifest.story_id,
            render_timestamp=datetime.utcnow().isoformat(),
            render_config={
                "width": self.config.output_width,
                "height": self.config.output_height,
                "fps": self.config.fps,
                "codec": self.config.video_codec,
                "crf": self.config.crf,
                "enable_music_bed": self.config.enable_music_bed,
            },
        )

        # Get FFmpeg version
        try:
            result = await asyncio.create_subprocess_exec(
                "ffmpeg", "-version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()
            render_report.ffmpeg_version = stdout.decode().split("\n")[0] if stdout else "unknown"
        except Exception:
            render_report.ffmpeg_version = "unavailable"

        if not self._ffmpeg_available:
            render_report.success = False
            render_report.errors = ["FFmpeg not available"]
            return RenderResult(
                success=False,
                errors=["FFmpeg not available"],
                render_report=render_report,
            )

        # Generate output filename
        if output_filename is None:
            output_filename = f"{manifest.story_id}_{video_id}.mp4"

        output_path = self.output_dir / output_filename

        # Create temporary directory for intermediate files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            shot_videos = []
            shot_reports = []

            # Render each shot
            for i, shot in enumerate(shots):
                # Find the image asset for this shot
                asset = manifest.get_asset_for_shot(shot.id, AssetType.IMAGE)

                if asset is None:
                    warnings.append(f"No image for shot {shot.id}")
                    continue

                shot_output = temp_path / f"shot_{i:04d}.mp4"
                result, shot_report = await self.render_shot(
                    shot,
                    asset.file_path,
                    str(shot_output),
                )

                shot_reports.append(shot_report)

                if result.success:
                    shot_videos.append(str(shot_output))
                else:
                    errors.extend(result.errors)

            render_report.shots = shot_reports

            if not shot_videos:
                render_report.success = False
                render_report.errors = errors or ["No shots rendered"]
                return RenderResult(
                    success=False,
                    errors=errors or ["No shots rendered"],
                    warnings=warnings,
                    render_report=render_report,
                )

            # Concatenate all shots (to temp file if adding audio)
            if self.config.enable_music_bed:
                video_only_path = temp_path / "video_only.mp4"
            else:
                video_only_path = output_path

            concat_result = await self._concat_videos(
                shot_videos,
                str(video_only_path),
            )

            if not concat_result.success:
                render_report.success = False
                render_report.errors = concat_result.errors
                return RenderResult(
                    success=False,
                    errors=concat_result.errors,
                    warnings=warnings,
                    render_report=render_report,
                )

            # Add music bed if enabled
            if self.config.enable_music_bed:
                total_duration = sum(s.duration_seconds for s in shots)
                audio_result = await self._add_music_bed(
                    str(video_only_path),
                    str(output_path),
                    total_duration,
                    scenes,
                )
                if audio_result.success:
                    render_report.audio_included = True
                    render_report.audio_path = audio_result.output_path
                    logger.info("music_bed_added", duration=total_duration)
                else:
                    warnings.append(f"Music bed failed: {audio_result.errors}")
                    # Fall back to video without audio
                    import shutil
                    shutil.copy(str(video_only_path), str(output_path))

        render_time = time.time() - start_time
        output_file = Path(output_path)

        # Calculate durations and drift
        total_planned = sum(s.duration_seconds for s in shots)
        total_rendered = await self._get_video_duration(str(output_path))
        duration_drift = total_rendered - total_planned

        render_report.total_planned_duration = total_planned
        render_report.total_rendered_duration = total_rendered
        render_report.duration_drift = duration_drift
        render_report.success = True

        logger.info(
            "video_rendered",
            output=str(output_path),
            shots=len(shot_videos),
            planned_duration=total_planned,
            actual_duration=total_rendered,
            drift=duration_drift,
            size_mb=output_file.stat().st_size / (1024 * 1024),
            render_time=render_time,
        )

        return RenderResult(
            success=True,
            output_path=str(output_path),
            duration_seconds=total_rendered,
            file_size_bytes=output_file.stat().st_size,
            render_time_seconds=render_time,
            shots_rendered=len(shot_videos),
            errors=errors,
            warnings=warnings,
            render_report=render_report,
        )

    async def _add_music_bed(
        self,
        video_path: str,
        output_path: str,
        duration: float,
        scenes: list[Scene] | None = None,
    ) -> RenderResult:
        """Add a music bed to the video.

        Generates an ambient music track based on scene moods and mixes it
        with the video.
        """
        try:
            # Generate music bed
            audio_generator = AudioBedGenerator(
                output_dir=str(self.output_dir / "audio")
            )
            music_path = audio_generator.generate_video_music_bed(
                scenes=scenes or [],
                total_duration=duration,
            )

            # Mix audio with video using FFmpeg
            cmd = [
                "ffmpeg",
                "-y",
                "-i", video_path,
                "-i", music_path,
                "-c:v", "copy",
                "-c:a", self.config.audio_codec,
                "-b:a", self.config.audio_bitrate,
                "-filter:a", f"volume={self.config.music_bed_volume}",
                "-shortest",
                output_path,
            ]

            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                return RenderResult(
                    success=False,
                    errors=[f"Audio mixing failed: {stderr.decode()[:500]}"],
                )

            return RenderResult(
                success=True,
                output_path=music_path,
            )

        except Exception as e:
            logger.warning("music_bed_error", error=str(e))
            return RenderResult(
                success=False,
                errors=[f"Music bed generation failed: {str(e)}"],
            )

    async def _concat_videos(
        self,
        video_paths: list[str],
        output_path: str,
    ) -> RenderResult:
        """Concatenate multiple video files."""
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            delete=False,
        ) as f:
            concat_file = f.name
            for path in video_paths:
                f.write(f"file '{path}'\n")

        try:
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file,
                "-c", "copy",
                output_path,
            ]

            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                return RenderResult(
                    success=False,
                    errors=[f"Concatenation failed: {stderr.decode()[:500]}"],
                )

            return RenderResult(success=True, output_path=output_path)

        finally:
            Path(concat_file).unlink(missing_ok=True)


async def render_draft_video(
    shots: list[Shot],
    manifest: AssetManifest,
    output_dir: str = "outputs/videos",
) -> RenderResult:
    """Convenience function to render a draft video."""
    renderer = VideoRenderer(output_dir=output_dir)
    return await renderer.render_video(shots, manifest)
