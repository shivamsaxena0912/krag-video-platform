# Founder Preview - Real High-Fidelity Demo

This directory contains a canonical validation run of the high-fidelity video generation pipeline.

## Prerequisites

1. **Set OpenAI API Key:**
   ```bash
   export OPENAI_API_KEY='your-key-here'
   ```

2. **Install dependencies:**
   ```bash
   pip install openai pillow
   ```

## Running the Canonical Validation

```bash
cd /Users/shivam/Desktop/krag-video-platform

# Run with founder_preview quality (real DALL-E images)
python scripts/run_pilot.py \
  --founder "Demo Founder" \
  --company "AcmeAI" \
  --scenario feature_launch \
  --brand acme \
  --render-quality founder_preview

# Optional: Add debug watermarks to verify REFERENCE shots
python scripts/run_pilot.py \
  --founder "Demo Founder" \
  --company "AcmeAI" \
  --scenario feature_launch \
  --brand acme \
  --render-quality founder_preview \
  --debug-fidelity
```

## Expected Output Structure

```
attempt_1/
├── assets/
│   ├── placeholder/
│   │   └── shot_001.png, shot_003.png, ...  (non-key shots)
│   ├── reference/
│   │   └── shot_002.png, shot_005.png, ...  (DALL-E generated)
│   └── manifest.json
├── final_video.mp4
├── video_cost_breakdown.json
├── render_report.json
├── founder_instructions.txt
├── what_to_expect.txt
└── approval_criteria.txt
```

## Which Shots Are High-Fidelity?

The fidelity policy selects these shots for DALL-E generation:
- **Hook shot** (shot 0) - The first impression
- **Climax shots** - Peak emotional moments
- **Establishing shots** (first 2) - Scene context
- **Resolution shot** (final shot) - The call to action

Default: **3-5 reference shots** per video, capped at $0.50.

## Why Only Those Shots?

1. **Cost control**: DALL-E images cost $0.04-$0.12 each
2. **Founder perception**: Key moments matter most
3. **Editing unchanged**: Timing/pacing remains consistent
4. **Quality where it counts**: Hook and CTA are high-fidelity

## What Founders Should Notice

When viewing the video:
1. **Opening shot** - Should look polished and professional
2. **Key moments** - Higher visual quality than transitions
3. **Final CTA** - Clean, high-quality call to action

The placeholder shots use styled gradients that maintain visual consistency but cost nothing to generate.

## Verification

Check `render_report.json` for fidelity proof:
```json
{
  "fidelity_proof": {
    "reference_shots": [0, 4, 8, 15],
    "reference_images_generated": true,
    "image_backend": "dalle3",
    "image_cost_usd": 0.32
  }
}
```

Check `video_cost_breakdown.json` for per-shot costs.

## Render Quality Presets

| Preset | Backend | Cost Cap | Reference Shots | Use Case |
|--------|---------|----------|-----------------|----------|
| `draft` | stub | $0 | 0 | Fast iteration |
| `founder_preview` | dalle3 | $0.50 | 3-5 | Founder feedback |
| `demo_only` | dalle3 | $1.00 | All key shots | Demos |
