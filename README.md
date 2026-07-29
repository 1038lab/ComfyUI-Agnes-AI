# ComfyUI Agnes-AI

ComfyUI custom nodes for the **Agnes AI API** — a free, cloud-based AI generation platform. Generate images, create videos, enhance prompts, and analyze visuals — all without a local GPU. Zero extra Python dependencies.

![Agnes-AI_nodes](example_workflows/Agnes-AI_Nodes.jpg)

## News & Updates

- **2026/07/29**: Update ComfyUI-Agnes-AI to **v1.1.0** ( [update.md](https://github.com/1038lab/ComfyUI-Agnes-AI/blob/main/updates.md#v110-20260729) )
![V1_1_0](https://github.com/user-attachments/assets/1ad90d3a-d2da-4c7c-bdd0-e8bfbe0d4616)

### v1.0.0

Initial release with Agnes-AI Image, Video, Text, and Config nodes.

## Why Agnes AI?

| | |
|---|---|
| **Free** | No token billing, no credit system — get a key and use it |
| **No GPU needed** | All computation runs on Agnes servers, your ComfyUI stays lightweight |
| **One API, many models** | Image gen, video gen, chat, vision — all through a single key |
| **Multi-image compose** | Up to 4 reference images for img2img composition |
| **Video generation** | Text-to-video, image-to-video, and keyframe interpolation |
| **Smart text presets** | Prompt enhancement, translation, art style extraction, image description |

> **Get a free API key:** [platform.agnes-ai.com](https://platform.agnes-ai.com)

## Features

- **Image Generation** — Text2img / img2img with up to 4 reference images. Auto-detects mode based on input connections. 1K / 2K / 4K resolution.
- **Video Generation** — Text-to-video, image-to-video, first-and-last-frame keyframe animation. 480p / 720p / 1080p, 3–18 seconds, configurable frame rate, negative prompt, and full frame/audio extraction.
- **Prompt Enhancement** — 4 built-in presets: enhance, translate, extract art style, describe image. Custom system prompt override. Vision-based presets with image input.
- **Settings Panel** — Configure API key, select default models, all from ComfyUI's built-in Settings Panel. Supports multiple API keys for load balancing.

## Installation

### Method 1: ComfyUI-Manager
Search `Agnes-AI` in ComfyUI-Manager and install.

### Method 2: Git Clone
```bash
cd ComfyUI/custom_nodes
git clone https://github.com/1038lab/ComfyUI-Agnes-AI
```
Restart ComfyUI.

### Method 3: Manual Install
Download the [latest release](https://github.com/1038lab/ComfyUI-Agnes-AI/releases), extract to `ComfyUI/custom_nodes/ComfyUI-Agnes-AI/`, restart ComfyUI.

No `pip install` needed — zero additional dependencies.

## API Key Setup

Open ComfyUI **Settings** (⚙️ gear icon) → search **"Agnes-AI"** → enter your API key.

- Multiple keys can be comma-separated for **round-robin load balancing**
- Alternatively, set the `AGNES_API_KEY` environment variable
- Key is saved to `agnes_config.json` and persists across restarts

Priority: **env var** (`AGNES_API_KEY`) > **saved config** (Settings Panel).

## Nodes

### 🖼️ Agnes-AI Image
Generate images from text, or compose new images from up to 4 reference images. Auto-detects text2img (no image input) vs img2img (images connected). When images are connected without a prompt, defaults to merging them into one cohesive composition. Supports 1K / 2K / 4K with various aspect ratios.

### 🎬 Agnes-AI Video
Three modes:
- **Text To Video** — generate video from text
- **Image To Video** — animate from a start frame
- **First and Last frame** — interpolate between two images

Supports 480p / 720p / 1080p, 3–18 seconds, configurable frame rate. 

**Inputs:**
- **prompt** — Description of the video to generate.
- **negative_prompt** — (Optional) Describe what to avoid in the generated video.
- **image** — Start frame (for Image To Video / First and Last frame).
- **end_frame** — End frame (for First and Last frame mode).
- **quality**, **aspect_ratio**, **duration**, **frame_rate**, **seed**.

**Outputs:**
- **video** — The generated video path or video object.
- **last_frame** — Automatically extracted last frame of the video (`IMAGE`).
- **frames** — The full sequence of extracted video frames as a batched `IMAGE` tensor (requires local `ffmpeg`).
- **audio** — Extracted audio track as a standard ComfyUI `AUDIO` waveform (requires local `ffmpeg`).

### ✏️ Agnes-AI Text
Process prompts through 4 built-in presets:

| Preset | Needs Image | Use Case |
|--------|-------------|----------|
| Prompt Enhance | No | Expand brief prompts with vivid visual context |
| Translate to English | No | Translate prompts while preserving visual details |
| Extract Art Style from Image | Yes | Analyze artistic style from a reference image |
| Image Detailed Description | Yes | Generate detailed AI-ready prompts from images |

Custom system prompt override supported for all presets. Supports `agnes-2.5-flash` (default), `agnes-2.5-pro-alpha` (paid model), `agnes-2.0-flash`, and `agnes-1.5-flash` configured via the Settings Panel.

## Example Workflows

_Coming soon — check the [example_workflows](./example_workflows) directory._

## Credits

- **Agnes AI** — Free API and model infrastructure. Get your key at [platform.agnes-ai.com](https://platform.agnes-ai.com)
- Created by [AILab](https://github.com/1038lab)

## License

GPL-3.0

If this custom node helps you, please ⭐ the repo!
