import base64
import os
import shutil
import tempfile
from io import BytesIO
from PIL import Image
import numpy as np
import torch

from agnes_api import (
    get_api_key, create_video, resolve_video_aspect_ratio,
    extract_input_items, VIDEO_ASPECT_RATIOS,
)

VIDEO_MODES = [
    "Text To Video",
    "Image To Video",
    "First and Last frame",
    "Reference (Images/Audio/Video)",
]

VIDEO_RESOLUTIONS = ["480P", "720P", "1080P", "1K", "2K"]

_VIDEO_TYPE = "STRING"
_ApiInput = None
_io = None
try:
    import comfy_api.latest as _cal
    _io = _cal.io
    _ApiInput = _cal.InputImpl
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


def _pil_to_b64(pil: Image.Image) -> str:
    buf = BytesIO()
    try:
        pil.save(buf, format="PNG")
        return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"
    finally:
        buf.close()


def _audio_to_b64(audio) -> str:
    """Convert ComfyUI AUDIO dict to Data URI base64 string."""
    if not audio:
        return None
    try:
        import io, wave
        waveform = None
        sample_rate = 16000
        if isinstance(audio, dict):
            waveform = audio.get("waveform")
            sample_rate = int(audio.get("sample_rate", 16000))
        if waveform is None:
            return None
        wv = waveform.cpu().numpy() if hasattr(waveform, "cpu") else np.asarray(waveform)
        if wv.size == 0:
            return None
        mono = np.clip(wv, -1.0, 1.0).astype(np.float32).reshape(-1)
        pcm = (mono * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm.tobytes())
        b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        return f"data:audio/wav;base64,{b64}"
    except Exception:
        return None


def _video_to_ref(video) -> dict:
    """Convert ComfyUI VIDEO object / VideoFromFile / filepath / dict / url to Agnes API video dict."""
    if video is None:
        return None
    # 1. ComfyUI VideoFromFile or similar object with get_stream_source()
    if hasattr(video, "get_stream_source"):
        try:
            source = video.get_stream_source()
        except Exception:
            source = None
        if hasattr(source, "getvalue"):
            data = source.getvalue()
            b64 = base64.b64encode(data).decode("utf-8")
            return {"url": f"data:video/mp4;base64,{b64}"}
        elif hasattr(source, "read"):
            data = source.read()
            b64 = base64.b64encode(data).decode("utf-8")
            return {"url": f"data:video/mp4;base64,{b64}"}
        elif isinstance(source, str) and source.strip():
            video = source.strip()
        elif isinstance(source, (bytes, bytearray)):
            b64 = base64.b64encode(source).decode("utf-8")
            return {"url": f"data:video/mp4;base64,{b64}"}

    MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB

    # 2. String path or URL
    if isinstance(video, str):
        v_str = video.strip()
        if v_str.startswith(("http://", "https://", "data:")):
            return {"url": v_str}
        if os.path.isfile(v_str):
            size = os.path.getsize(v_str)
            if size > MAX_VIDEO_SIZE:
                raise ValueError(f"Reference video too large ({size // (1024*1024)}MB). Max allowed: 100MB")
            try:
                with open(v_str, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                return {"url": f"data:video/mp4;base64,{b64}"}
            except Exception:
                pass

    # 3. Dict with url / path / filename
    if isinstance(video, dict):
        url = video.get("url") or video.get("path") or video.get("filename") or video.get("name")
        if url:
            return _video_to_ref(url)

    # 4. Folder paths lookup if filename given
    try:
        import folder_paths
        annotated = folder_paths.get_annotated_filepath(str(video))
        if annotated and os.path.isfile(annotated):
            size = os.path.getsize(annotated)
            if size > MAX_VIDEO_SIZE:
                raise ValueError(f"Reference video too large ({size // (1024*1024)}MB). Max allowed: 100MB")
            with open(annotated, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            return {"url": f"data:video/mp4;base64,{b64}"}
    except Exception:
        pass

    return None


def _get_output_dir() -> str:
    try:
        from folder_paths import get_temp_directory
        base = get_temp_directory()
    except ImportError:
        base = tempfile.gettempdir()
    p = os.path.join(base, "agnes_videos")
    os.makedirs(p, exist_ok=True)
    return p


_BaseNode = getattr(_io, "ComfyNode", object) if _io is not None else object


class AgnesVideo(_BaseNode):
    CATEGORY = "🧪AILab/⚡Agnes-AI"
    RETURN_TYPES = (_VIDEO_TYPE, "IMAGE", "IMAGE", "AUDIO")
    RETURN_NAMES = ("video", "last_frame", "frames", "audio")
    FUNCTION = "execute"
    SEARCH_ALIASES = [
        "agnes", "txt2video", "img2video", "text to video", "image to video",
        "first and last frame", "video reference", "generate video",
    ]

    @classmethod
    def define_schema(cls):
        if _io is None:
            return None
        return _io.Schema(
            node_id="AgnesVideo",
            display_name="Agnes-AI Video",
            category="🧪AILab/⚡Agnes-AI",
            description="Agnes-AI Video Generator: supports Text To Video, Image To Video, First and Last frame, and Reference (Images/Audio/Video) with auto-growing dynamic input slots.",
            inputs=[
                _io.Combo.Input("mode", options=VIDEO_MODES, default="Text To Video",
                                tooltip="Text To Video: generate purely from prompt\nImage To Video: animate starting frame\nFirst and Last frame: interpolate between frames\nReference (Images/Audio/Video): dynamic reference materials"),
                _io.String.Input("prompt", multiline=True, default="",
                                 tooltip="Video content description. In Reference mode, refer to <Picture N>, <Audio N>, <Video N>"),
                _io.Combo.Input("quality", options=VIDEO_RESOLUTIONS, default="720P",
                                tooltip="Resolution tier: 480P, 720P, 1080P, 1K, 2K. Note: Flash model auto-downgrades to 720P per official API specification."),
                _io.Combo.Input("aspect_ratio", options=VIDEO_ASPECT_RATIOS, default="auto",
                                tooltip="Output aspect ratio. 'auto' matches input image ratio"),
                _io.Int.Input("duration", default=5, min=4, max=12,
                              tooltip="Video duration in seconds (4-12s)"),
                _io.Int.Input("seed", default=0, min=0, max=0xffffffffffffffff,
                              control_after_generate=True,
                              tooltip="Random seed (0 = random)"),
                _io.Image.Input("first_image", display_name="first_image", optional=True,
                                tooltip="First image / Start frame (Image To Video & First and Last frame mode) or Primary reference image (Reference mode)"),
                _io.Image.Input("end_frame", display_name="end_frame", optional=True,
                                tooltip="End frame (First and Last frame mode)"),
                _io.Autogrow.Input(
                    id="ref_images",
                    template=_io.Autogrow.TemplatePrefix(
                        input=_io.Image.Input("ref_image", optional=True, tooltip="Reference image"),
                        prefix="ref_image_", min=0, max=5
                    ),
                    display_name="Reference Images",
                    optional=True,
                    tooltip="Additional reference images (starts with ref_image_0, up to 5 total, auto-grows as connected)"
                ),
                _io.Autogrow.Input(
                    id="ref_audios",
                    template=_io.Autogrow.TemplatePrefix(
                        input=_io.Audio.Input("ref_audio", optional=True, tooltip="Reference audio"),
                        prefix="ref_audio_", min=0, max=3
                    ),
                    display_name="Reference Audio",
                    optional=True,
                    tooltip="Reference audio tracks (starts with ref_audio_0, up to 3 total, auto-grows as connected)"
                ),
                _io.Video.Input("ref_video", display_name="ref_video", optional=True,
                                tooltip="Reference video (1 video max, supported on agnes-video-2.5 standard model)"),
            ],
            outputs=[
                _io.Video.Output("video", display_name="video"),
                _io.Image.Output("last_frame", display_name="last_frame"),
                _io.Image.Output("frames", display_name="frames"),
                _io.Audio.Output("audio", display_name="audio"),
            ],
        )

    @classmethod
    def execute(cls, **kwargs):
        inst = cls()
        res = inst._execute_internal(**kwargs)
        if _io is not None and hasattr(_io, "NodeOutput"):
            return _io.NodeOutput(*res)
        return res

    @classmethod
    def generate(cls, **kwargs):
        return cls.execute(**kwargs)

    def _execute_internal(self, **kwargs):
        mode = kwargs.get("mode", "Text To Video")
        prompt = kwargs.get("prompt", "")
        quality = kwargs.get("quality", "720P")
        aspect_ratio = kwargs.get("aspect_ratio", "auto")
        duration = kwargs.get("duration", 5)
        seed = kwargs.get("seed", 0)
        first_image = kwargs.get("first_image") if kwargs.get("first_image") is not None else kwargs.get("image")
        end_frame = kwargs.get("end_frame")

        key = get_api_key("AgnesVideo")
        if not key:
            raise ValueError("API key required — set it in ComfyUI Settings Panel → Agnes-AI")

        out = _get_output_dir()
        try:
            actual_seed = int(seed) if seed is not None and str(seed).strip() else 0
        except (ValueError, TypeError):
            actual_seed = 0
        actual_seed = actual_seed if actual_seed > 0 else None
        img_shape = first_image.shape if first_image is not None else None
        final_aspect_ratio = resolve_video_aspect_ratio(aspect_ratio, img_shape)

        first_frame_b64 = None
        end_frame_b64 = None
        images_b64 = None
        audios_b64 = None
        videos_payload = None

        if mode == "Text To Video":
            api_mode = "text"
        elif mode == "Image To Video":
            api_mode = "keyframe"
            if first_image is None:
                ref_imgs = extract_input_items(kwargs, "ref_images", "ref_image_")
                if ref_imgs:
                    first_image = ref_imgs[0]
            if first_image is None:
                raise ValueError("first_image required for Image To Video")
            first_frame_b64 = _pil_to_b64(_tensor_to_pil(first_image))
        elif mode == "First and Last frame":
            api_mode = "keyframe"
            if first_image is None and end_frame is None:
                ref_imgs = extract_input_items(kwargs, "ref_images", "ref_image_")
                if ref_imgs:
                    first_image = ref_imgs[0]
            if first_image is None and end_frame is None:
                raise ValueError("At least first_image or end_frame required for First and Last frame mode")
            if first_image is not None:
                first_frame_b64 = _pil_to_b64(_tensor_to_pil(first_image))
            if end_frame is not None:
                end_frame_b64 = _pil_to_b64(_tensor_to_pil(end_frame))
        elif mode == "Reference (Images/Audio/Video)":
            api_mode = "reference"
            # Collect images
            raw_images = []
            if first_image is not None:
                raw_images.append(first_image)
            raw_images.extend(extract_input_items(kwargs, "ref_images", "ref_image_"))
            collected_img = [_pil_to_b64(_tensor_to_pil(r)) for r in raw_images if r is not None]
            if collected_img:
                images_b64 = collected_img[:5]

            # Collect audios
            raw_audios = []
            if kwargs.get("audio") is not None:
                raw_audios.append(kwargs["audio"])
            raw_audios.extend(extract_input_items(kwargs, "ref_audios", "ref_audio_"))
            collected_aud = [_audio_to_b64(a) for a in raw_audios if a is not None]
            collected_aud = [a for a in collected_aud if a]
            if collected_aud:
                audios_b64 = collected_aud[:3]

            # Collect video (1 video max)
            raw_video = kwargs.get("ref_video")
            if raw_video is None:
                for k in sorted(kwargs.keys()):
                    if (k.startswith("ref_video") or k.startswith("video")) and kwargs[k] is not None:
                        raw_video = kwargs[k]
                        break
            if raw_video is not None:
                v_dict = _video_to_ref(raw_video)
                if v_dict:
                    videos_payload = [v_dict]

            if not images_b64 and not audios_b64 and not videos_payload:
                raise ValueError("Reference mode requires at least one reference image, audio, or video")

        p = str(prompt).strip()
        if not p:
            if mode == "Text To Video":
                raise ValueError("Prompt required for Text To Video")
            elif mode == "Image To Video":
                p = "Animate the image with natural, smooth cinematic motion and movement"
            elif mode == "First and Last frame":
                p = "Smoothly interpolate and transition between the first frame and the last frame with natural cinematic motion"
            elif mode == "Reference (Images/Audio/Video)":
                p = "Generate a cinematic video adhering to the visual style and motion of the reference materials"
            else:
                p = "Cinematic video with natural movement and lighting"

        path = create_video(
            api_key=key,
            prompt=p,
            mode=api_mode,
            first_frame_b64=first_frame_b64,
            end_frame_b64=end_frame_b64,
            images_b64=images_b64,
            audios_b64=audios_b64,
            videos_payload=videos_payload,
            quality=quality,
            aspect_ratio=final_aspect_ratio,
            seconds=int(duration),
            seed=actual_seed,
            output_dir=out,
        )

        # Extract all frames
        frames = _extract_all_frames(path)
        last_frame = frames[-1:] if len(frames) > 0 else _pil_to_tensor(Image.new("RGB", (64, 64), (0, 0, 0)))

        # Extract audio
        audio_out = _extract_audio(path)

        video_out = _ApiInput.VideoFromFile(path) if (_ApiInput is not None and hasattr(_ApiInput, "VideoFromFile")) else path
        return (video_out, last_frame, frames, audio_out)


def _extract_all_frames(video_path: str):
    """Extract all frames from the video as a batched IMAGE tensor."""
    tmp_dir = tempfile.mkdtemp(prefix="agnes_frames_")
    try:
        import subprocess
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
        return torch.cat(tensors, dim=0)
    except Exception:
        return _pil_to_tensor(Image.new("RGB", (64, 64), (0, 0, 0)))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _extract_audio(video_path: str):
    """Extract audio from the video and return as ComfyUI AUDIO dict."""
    tmp_path = None
    try:
        import subprocess
        import torchaudio
        tmp_audio = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = tmp_audio.name
        tmp_audio.close()
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", video_path,
             "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
             tmp_path],
            capture_output=True, timeout=60,
        )
        if result.returncode != 0:
            return {"waveform": torch.zeros(1, 2, 0), "sample_rate": 44100}
        waveform, sample_rate = torchaudio.load(tmp_path)
        # ComfyUI AUDIO format: {"waveform": (batch, channels, samples), "sample_rate": int}
        if waveform.dim() == 2:
            waveform = waveform.unsqueeze(0)  # Add batch dimension
        return {"waveform": waveform, "sample_rate": sample_rate}
    except Exception:
        return {"waveform": torch.zeros(1, 2, 0), "sample_rate": 44100}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


NODE_CLASS_MAPPINGS = {"AgnesVideo": AgnesVideo}
NODE_DISPLAY_NAME_MAPPINGS = {"AgnesVideo": "Agnes-AI Video"}
