import base64, os, tempfile
from io import BytesIO
from PIL import Image
import numpy as np
import torch

from agnes_api import (
    get_api_key, create_video, resolve_size, duration_to_num_frames,
    extract_last_frame,
    QUALITY_VIDEO, ASPECT_RATIOS,
)

VIDEO_MODES = ["Text To Video", "Image To Video", "First and Last frame"]

_VIDEO_TYPE = "STRING"
try:
    from comfy_api.latest import InputImpl as _ApiInput
    if hasattr(_ApiInput, "VideoFromFile"):
        _VIDEO_TYPE = "VIDEO"
except Exception:
    pass


def _tensor_to_pil(tensor, index=0) -> Image.Image:
    i = tensor[index].cpu().numpy()
    return Image.fromarray((i * 255).astype(np.uint8))


def _pil_to_tensor(img: Image.Image):
    a = np.array(img.convert("RGB"), dtype=np.float32) / 255.0
    return torch.from_numpy(a).unsqueeze(0)


def _get_output_dir() -> str:
    try:
        from folder_paths import get_temp_directory
        base = get_temp_directory()
    except ImportError:
        base = tempfile.gettempdir()
    p = os.path.join(base, "agnes_videos")
    os.makedirs(p, exist_ok=True)
    return p


class AgnesVideo:
    CATEGORY = "🧪AILab/⚡Agnes-AI"
    RETURN_TYPES = (_VIDEO_TYPE, "IMAGE", "IMAGE", "AUDIO")
    RETURN_NAMES = ("video", "last_frame", "frames", "audio")
    FUNCTION = "generate"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mode": (VIDEO_MODES, {
                    "default": "Text To Video",
                    "tooltip": "Text To Video: generate from prompt\n"
                               "Image To Video: animate from start frame\n"
                               "First and Last frame: interpolate between two frames",
                }),
                "prompt": ("STRING", {
                    "default": "", "multiline": True,
                    "placeholder": "Cinematic camera movement, natural motion.",
                    "tooltip": "Description of the video to generate",
                }),
                "quality": (list(QUALITY_VIDEO.keys()), {
                    "default": "720p",
                    "tooltip": "Output resolution",
                }),
                "aspect_ratio": (ASPECT_RATIOS, {
                    "default": "auto",
                    "tooltip": "Output aspect ratio. 'auto' matches input image ratio when img2video/keyframes",
                }),
                "duration": ("FLOAT", {
                    "default": 5.0, "min": 3.0, "max": 18.0, "step": 0.5,
                    "tooltip": "Video duration in seconds (3-18)",
                }),
                "frame_rate": ("INT", {
                    "default": 24, "min": 1, "max": 60, "step": 1,
                    "tooltip": "Frames per second",
                }),
                "seed": ("INT", {
                    "default": 0, "min": 0, "max": 2147483647, "step": 1,
                    "tooltip": "Random seed (0 = random)",
                }),
            },
            "optional": {
                "image": ("IMAGE", {
                    "tooltip": "Start frame for Image To Video / First and Last frame",
                }),
                "end_frame": ("IMAGE", {
                    "tooltip": "End frame for First and Last frame mode",
                }),
                "negative_prompt": ("STRING", {
                    "default": "", "multiline": True,
                    "placeholder": "Elements to avoid in the video...",
                    "tooltip": "Negative prompt — describes what to avoid in the generated video",
                }),
            },
        }

    def generate(self, mode="Text To Video", prompt="", quality="720p",
                 aspect_ratio="auto", duration=5.0, frame_rate=24,
                 seed=0, image=None, end_frame=None, negative_prompt=""):
        key = get_api_key()
        if not key:
            raise ValueError("API key required — set it in ComfyUI Settings Panel → Agnes-AI")
        if not prompt.strip() and mode == "Text To Video":
            raise ValueError("Prompt required for Text To Video")

        out = _get_output_dir()
        actual_seed = seed if seed > 0 else None
        num_frames = duration_to_num_frames(duration, frame_rate)
        img_shape = image.shape if image is not None else None
        size = resolve_size(quality, aspect_ratio, QUALITY_VIDEO, img_shape)

        mode_map = {
            "Text To Video": "text2video",
            "Image To Video": "img2video",
            "First and Last frame": "keyframes",
        }
        api_mode = mode_map.get(mode, "text2video")

        def pil_to_b64(pil):
            buf = BytesIO()
            pil.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode()

        img_b64 = pil_to_b64(_tensor_to_pil(image)) if image is not None else None
        end_b64 = pil_to_b64(_tensor_to_pil(end_frame)) if end_frame is not None else None

        path = create_video(key, prompt.strip(), mode=api_mode,
                            image_b64=img_b64, end_frame_b64=end_b64,
                            size=size, num_frames=num_frames,
                            frame_rate=frame_rate, seed=actual_seed,
                            negative_prompt=negative_prompt.strip(),
                            output_dir=out)

        # Last frame extraction
        last_frame_img = extract_last_frame(path)
        if last_frame_img is not None:
            last_frame = _pil_to_tensor(last_frame_img)
        else:
            last_frame = _pil_to_tensor(Image.new("RGB", (64, 64), (0, 0, 0)))

        # Extract all frames
        frames = _extract_all_frames(path)

        # Extract audio
        audio = _extract_audio(path)

        video_out = _ApiInput.VideoFromFile(path) if _VIDEO_TYPE == "VIDEO" else path
        return (video_out, last_frame, frames, audio)


def _extract_all_frames(video_path: str):
    """Extract all frames from the video as a batched IMAGE tensor."""
    try:
        import subprocess
        tmp_dir = tempfile.mkdtemp(prefix="agnes_frames_")
        subprocess.run(
            ["ffmpeg", "-y", "-i", video_path,
             os.path.join(tmp_dir, "frame_%06d.png")],
            capture_output=True, timeout=120,
        )
        frame_files = sorted(
            f for f in os.listdir(tmp_dir) if f.endswith(".png")
        )
        if not frame_files:
            return _pil_to_tensor(Image.new("RGB", (64, 64), (0, 0, 0)))
        tensors = []
        for fname in frame_files:
            img = Image.open(os.path.join(tmp_dir, fname)).convert("RGB")
            tensors.append(_pil_to_tensor(img))
        # Clean up temp files
        for fname in frame_files:
            try:
                os.unlink(os.path.join(tmp_dir, fname))
            except OSError:
                pass
        try:
            os.rmdir(tmp_dir)
        except OSError:
            pass
        return torch.cat(tensors, dim=0)
    except Exception:
        return _pil_to_tensor(Image.new("RGB", (64, 64), (0, 0, 0)))


def _extract_audio(video_path: str):
    """Extract audio from the video and return as ComfyUI AUDIO dict."""
    try:
        import subprocess
        import torchaudio
        tmp_audio = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_audio.close()
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", video_path,
             "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
             tmp_audio.name],
            capture_output=True, timeout=60,
        )
        if result.returncode != 0:
            os.unlink(tmp_audio.name)
            return {"waveform": torch.zeros(1, 2, 0), "sample_rate": 44100}
        waveform, sample_rate = torchaudio.load(tmp_audio.name)
        os.unlink(tmp_audio.name)
        # ComfyUI AUDIO format: {"waveform": (batch, channels, samples), "sample_rate": int}
        if waveform.dim() == 2:
            waveform = waveform.unsqueeze(0)  # Add batch dimension
        return {"waveform": waveform, "sample_rate": sample_rate}
    except Exception:
        return {"waveform": torch.zeros(1, 2, 0), "sample_rate": 44100}


NODE_CLASS_MAPPINGS = {"AgnesVideo": AgnesVideo}
NODE_DISPLAY_NAME_MAPPINGS = {"AgnesVideo": "Agnes-AI Video"}
