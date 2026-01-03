"""Asset generation and video rendering."""

from src.generation.manifest import (
    AssetManifest,
    AssetRequirement,
    ManifestStatus,
    create_manifest_from_shots,
)
from src.generation.placeholder import (
    PlaceholderGenerator,
    create_placeholder_image,
    create_placeholder_with_visual_spec,
)
from src.generation.reference_generator import (
    VisualReferenceGenerator,
    ImageGeneratorBackend,
    StubReferenceBackend,
    create_reference_generator,
)
from src.generation.asset_generator import (
    MixedFidelityAssetGenerator,
    count_by_fidelity,
)
from src.generation.fidelity_policy import (
    FidelityPolicyConfig,
    DefaultFidelityPolicy,
    apply_fidelity_by_role,
    mark_shots_reference,
)
from src.generation.renderer import (
    VideoRenderer,
    RenderConfig,
    RenderResult,
    RenderReport,
    ShotRenderReport,
    KenBurnsDirection,
    KenBurnsParams,
    motion_to_ken_burns,
    visual_spec_to_ken_burns,
    render_draft_video,
)
from src.generation.audio_generator import (
    AudioBedGenerator,
    generate_music_bed,
    generate_scene_transition_sound,
)

__all__ = [
    # Manifest
    "AssetManifest",
    "AssetRequirement",
    "ManifestStatus",
    "create_manifest_from_shots",
    # Placeholder
    "PlaceholderGenerator",
    "create_placeholder_image",
    "create_placeholder_with_visual_spec",
    # Reference Generator
    "VisualReferenceGenerator",
    "ImageGeneratorBackend",
    "StubReferenceBackend",
    "create_reference_generator",
    # Mixed Fidelity Generator
    "MixedFidelityAssetGenerator",
    "count_by_fidelity",
    # Fidelity Policy
    "FidelityPolicyConfig",
    "DefaultFidelityPolicy",
    "apply_fidelity_by_role",
    "mark_shots_reference",
    # Renderer
    "VideoRenderer",
    "RenderConfig",
    "RenderResult",
    "RenderReport",
    "ShotRenderReport",
    "KenBurnsDirection",
    "KenBurnsParams",
    "motion_to_ken_burns",
    "visual_spec_to_ken_burns",
    "render_draft_video",
    # Audio
    "AudioBedGenerator",
    "generate_music_bed",
    "generate_scene_transition_sound",
]
