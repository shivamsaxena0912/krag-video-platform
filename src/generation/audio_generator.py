"""Audio generator for music beds and sound effects."""

from __future__ import annotations

import math
import struct
import tempfile
import wave
from pathlib import Path

from src.common.logging import get_logger
from src.common.models import MusicPlan, Scene

logger = get_logger(__name__)


# Mood to musical characteristics mapping
MOOD_AUDIO_PROFILES = {
    "tension": {"base_freq": 110, "harmonics": [1.0, 0.5, 0.3], "lfo_rate": 0.5, "volume": 0.4},
    "sorrow": {"base_freq": 98, "harmonics": [1.0, 0.6, 0.2], "lfo_rate": 0.2, "volume": 0.35},
    "hope": {"base_freq": 196, "harmonics": [1.0, 0.4, 0.3, 0.2], "lfo_rate": 0.3, "volume": 0.4},
    "triumph": {"base_freq": 220, "harmonics": [1.0, 0.5, 0.4, 0.3], "lfo_rate": 0.4, "volume": 0.5},
    "contemplative": {"base_freq": 130, "harmonics": [1.0, 0.3, 0.2], "lfo_rate": 0.15, "volume": 0.3},
    "action": {"base_freq": 147, "harmonics": [1.0, 0.6, 0.4, 0.3], "lfo_rate": 0.8, "volume": 0.5},
    "mystery": {"base_freq": 104, "harmonics": [1.0, 0.4, 0.3, 0.2], "lfo_rate": 0.25, "volume": 0.35},
    "neutral": {"base_freq": 130, "harmonics": [1.0, 0.3, 0.2], "lfo_rate": 0.2, "volume": 0.3},
}


def _generate_drone_sample(
    duration_seconds: float,
    sample_rate: int = 44100,
    base_freq: float = 130.0,
    harmonics: list[float] | None = None,
    lfo_rate: float = 0.2,
    volume: float = 0.3,
) -> list[int]:
    """Generate an ambient drone sample with harmonics and LFO modulation.

    Creates a layered pad sound suitable for documentary background music.
    """
    if harmonics is None:
        harmonics = [1.0, 0.3, 0.2]

    num_samples = int(duration_seconds * sample_rate)
    samples = []

    for i in range(num_samples):
        t = i / sample_rate
        sample = 0.0

        # Generate harmonics
        for h_idx, h_amp in enumerate(harmonics):
            freq = base_freq * (h_idx + 1)
            # Add slight detuning for richness
            detune = 1.0 + (h_idx * 0.002)
            sample += h_amp * math.sin(2 * math.pi * freq * detune * t)

        # Apply LFO for movement
        lfo = 0.5 + 0.5 * math.sin(2 * math.pi * lfo_rate * t)
        sample *= 0.7 + 0.3 * lfo

        # Apply volume envelope (fade in/out)
        fade_samples = int(2.0 * sample_rate)  # 2 second fade
        if i < fade_samples:
            sample *= i / fade_samples
        elif i > num_samples - fade_samples:
            sample *= (num_samples - i) / fade_samples

        # Normalize and convert to 16-bit
        sample = int(sample * volume * 32767)
        sample = max(-32767, min(32767, sample))
        samples.append(sample)

    return samples


def _apply_crossfade(
    samples: list[int],
    fade_duration_seconds: float,
    sample_rate: int = 44100,
) -> list[int]:
    """Apply crossfade at the end for seamless looping or scene transitions."""
    fade_samples = int(fade_duration_seconds * sample_rate)
    if fade_samples * 2 > len(samples):
        return samples

    result = samples.copy()

    # Fade out at end
    for i in range(fade_samples):
        idx = len(result) - fade_samples + i
        factor = 1.0 - (i / fade_samples)
        result[idx] = int(result[idx] * factor)

    return result


def generate_music_bed(
    duration_seconds: float,
    mood: str = "neutral",
    output_path: str | None = None,
    sample_rate: int = 44100,
) -> str:
    """Generate a placeholder music bed based on mood.

    Returns the path to the generated WAV file.
    """
    # Get audio profile for mood
    profile = MOOD_AUDIO_PROFILES.get(mood.lower(), MOOD_AUDIO_PROFILES["neutral"])

    logger.debug(
        "generating_music_bed",
        duration=duration_seconds,
        mood=mood,
        base_freq=profile["base_freq"],
    )

    # Generate samples
    samples = _generate_drone_sample(
        duration_seconds=duration_seconds,
        sample_rate=sample_rate,
        base_freq=profile["base_freq"],
        harmonics=profile["harmonics"],
        lfo_rate=profile["lfo_rate"],
        volume=profile["volume"],
    )

    # Apply crossfade for smooth ending
    samples = _apply_crossfade(samples, 1.0, sample_rate)

    # Determine output path
    if output_path is None:
        temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        output_path = temp_file.name
        temp_file.close()

    # Write WAV file
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with wave.open(output_path, "w") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)

        # Pack samples as 16-bit signed integers
        packed = struct.pack(f"<{len(samples)}h", *samples)
        wav_file.writeframes(packed)

    logger.info(
        "music_bed_generated",
        path=output_path,
        duration=duration_seconds,
        mood=mood,
    )

    return output_path


def generate_scene_transition_sound(
    from_mood: str,
    to_mood: str,
    duration_seconds: float = 2.0,
    output_path: str | None = None,
    sample_rate: int = 44100,
) -> str:
    """Generate a transition sound that bridges two scene moods.

    Creates a crossfade between the audio characteristics of two moods.
    """
    from_profile = MOOD_AUDIO_PROFILES.get(from_mood.lower(), MOOD_AUDIO_PROFILES["neutral"])
    to_profile = MOOD_AUDIO_PROFILES.get(to_mood.lower(), MOOD_AUDIO_PROFILES["neutral"])

    num_samples = int(duration_seconds * sample_rate)
    samples = []

    for i in range(num_samples):
        t = i / sample_rate
        progress = i / num_samples  # 0 to 1 transition

        # Interpolate between profiles
        freq = from_profile["base_freq"] * (1 - progress) + to_profile["base_freq"] * progress
        vol = from_profile["volume"] * (1 - progress) + to_profile["volume"] * progress
        lfo = from_profile["lfo_rate"] * (1 - progress) + to_profile["lfo_rate"] * progress

        # Generate blended sample
        sample = 0.0
        for h_idx in range(3):
            sample += math.sin(2 * math.pi * freq * (h_idx + 1) * t) * (0.5 ** h_idx)

        # Apply LFO
        lfo_mod = 0.5 + 0.5 * math.sin(2 * math.pi * lfo * t)
        sample *= 0.7 + 0.3 * lfo_mod

        # Apply crossfade envelope (smooth transition)
        sample *= vol * math.sin(math.pi * progress)  # Sine window for smooth in/out

        sample = int(sample * 32767)
        sample = max(-32767, min(32767, sample))
        samples.append(sample)

    if output_path is None:
        temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        output_path = temp_file.name
        temp_file.close()

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with wave.open(output_path, "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        packed = struct.pack(f"<{len(samples)}h", *samples)
        wav_file.writeframes(packed)

    logger.debug(
        "transition_sound_generated",
        from_mood=from_mood,
        to_mood=to_mood,
        duration=duration_seconds,
    )

    return output_path


class AudioBedGenerator:
    """Generator for continuous music bed across a video."""

    def __init__(self, output_dir: str = "outputs/audio"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_video_music_bed(
        self,
        scenes: list[Scene],
        total_duration: float,
    ) -> str:
        """Generate a continuous music bed for the entire video.

        Creates a blended music track that transitions between scene moods.
        Returns path to the combined WAV file.
        """
        if not scenes:
            # Fallback to neutral drone
            return generate_music_bed(
                total_duration,
                mood="neutral",
                output_path=str(self.output_dir / "music_bed.wav"),
            )

        # For simplicity, use the dominant mood from all scenes
        # Scene.emotional_beat.primary_emotion contains the mood
        mood_counts: dict[str, float] = {}
        for scene in scenes:
            mood = scene.emotional_beat.primary_emotion if scene.emotional_beat else "neutral"
            # Weight by number of shots (approximates duration contribution)
            mood_counts[mood] = mood_counts.get(mood, 0) + 1

        dominant_mood = max(mood_counts, key=mood_counts.get) if mood_counts else "neutral"

        logger.info(
            "generating_video_music_bed",
            total_duration=total_duration,
            dominant_mood=dominant_mood,
            scene_count=len(scenes),
        )

        return generate_music_bed(
            total_duration,
            mood=dominant_mood,
            output_path=str(self.output_dir / "music_bed.wav"),
        )

    def generate_scene_bridges(
        self,
        scenes: list[Scene],
        scene_end_times: list[float],
    ) -> list[tuple[float, str]]:
        """Generate transition sounds between scenes.

        Returns list of (timestamp, audio_path) tuples.
        """
        bridges = []

        for i in range(len(scenes) - 1):
            from_mood = scenes[i].emotional_beat.primary_emotion if scenes[i].emotional_beat else "neutral"
            to_mood = scenes[i + 1].emotional_beat.primary_emotion if scenes[i + 1].emotional_beat else "neutral"

            # Only create bridge if moods differ significantly
            if from_mood != to_mood:
                bridge_path = str(self.output_dir / f"bridge_{i}_{i+1}.wav")
                generate_scene_transition_sound(
                    from_mood=from_mood,
                    to_mood=to_mood,
                    duration_seconds=1.5,
                    output_path=bridge_path,
                )
                # Bridge starts 0.75s before scene end
                bridge_time = scene_end_times[i] - 0.75
                bridges.append((bridge_time, bridge_path))

        return bridges
