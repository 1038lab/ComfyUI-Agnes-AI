import base64, json, os, tempfile, time
import urllib.error, urllib.request
from io import BytesIO
from pathlib import Path

API_BASE = "https://apihub.agnes-ai.com/v1"
POLL_BASE = "https://apihub.agnes-ai.com"
PLUGIN_DIR = Path(__file__).parent
CONFIG_FILE = PLUGIN_DIR / "agnes_config.json"

QUALITY_IMAGE = {"1K": 1024, "2K": 2048, "4K": 4096}
QUALITY_VIDEO = {"480p": 480, "720p": 720, "1080p": 1080}
ASPECT_RATIOS = [
    "auto", "1:1", "2:3", "3:4", "4:5", "9:16", "9:21",
    "3:2", "4:3", "5:4", "16:9", "21:9",
]

TEXT_MODELS = ["agnes-2.0-flash", "agnes-1.5-flash"]
IMAGE_MODELS = ["agnes-image-2.1-flash", "agnes-image-2.0-flash"]
VIDEO_MODELS = ["agnes-video-v2.0"]

DEFAULT_STYLES = {
    "Prompt Enhance": {
        "system_prompt": (
            "You are an expert prompt engineer for AI image generation. Expand and enrich "
            "the given prompt with vivid visual context: subject details, lighting, color palette, "
            "composition, mood, camera angle, and style. Keep it concise but powerful."
        ),
        "requires_image": False,
    },
    "Translate to English": {
        "system_prompt": (
            "Translate the following prompt to English. Preserve all visual details, "
            "style, lighting, composition, and quality terms. Return ONLY the translation."
        ),
        "requires_image": False,
    },
    "Extract Art Style from Image": {
        "system_prompt": (
            "Analyze the artistic style of this image. Identify the art movement, technique, "
            "color palette, brushwork, lighting approach, and composition style. "
            "Output ONLY a prompt that captures this artistic style for AI image generation. "
            "Do not describe the image content or subject matter."
        ),
        "requires_image": True,
    },
    "Image Detailed Description": {
        "system_prompt": (
            "You are an expert at analyzing images and writing AI image generation prompts. "
            "Describe this image in extreme detail: subject, composition, lighting, color palette, "
            "style, mood, camera angle, depth of field, textures, and distinctive elements. "
            "Output ONLY the prompt, no commentary."
        ),
        "requires_image": True,
    },

}

# ── Config ───────────────────────────────────────────────────────────

def _load_config() -> dict:
    try:
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        pass
    return {}

def _save_config(cfg: dict):
    try:
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
    except OSError:
        pass

def _parse_keys(raw: str) -> list[str]:
    return [k.strip() for k in raw.replace(";", ",").replace("\n", ",").split(",") if k.strip()]


def get_api_key(widget_key: str = "") -> str:
    cfg = _load_config()
    if widget_key.strip():
        cfg["api_key"] = widget_key.strip()
        cfg["api_key_index"] = 0
        _save_config(cfg)
        return widget_key.strip().split(",")[0].strip()

    env = os.environ.get("AGNES_API_KEY") or os.environ.get("AGNES_API_TOKEN") or ""
    if env:
        keys = _parse_keys(env)
        return keys[0]

    raw = cfg.get("api_key", "")
    if not raw:
        return ""
    keys = _parse_keys(raw)
    if len(keys) == 1:
        return keys[0]
    idx = cfg.get("api_key_index", 0)
    key = keys[idx % len(keys)]
    cfg["api_key_index"] = (idx + 1) % len(keys)
    _save_config(cfg)
    return key

def get_model(model_type: str, widget_model: str = "") -> str:
    if widget_model.strip():
        return widget_model.strip()
    cfg = _load_config()
    return cfg.get("models", {}).get(model_type, _default_model(model_type))

def _default_model(model_type: str) -> str:
    return {
        "image": "agnes-image-2.1-flash",
        "video": "agnes-video-v2.0",
        "chat": "agnes-2.0-flash",
    }.get(model_type, "")

def get_styles() -> dict:
    cfg = _load_config()
    saved = cfg.get("prompt_styles")
    if saved is None:
        return DEFAULT_STYLES
    changed = False
    for key in list(saved.keys()):
        if key not in DEFAULT_STYLES:
            del saved[key]
            changed = True
    for key, val in DEFAULT_STYLES.items():
        if key not in saved:
            saved[key] = val
            changed = True
    if changed:
        cfg["prompt_styles"] = saved
        _save_config(cfg)
    return saved

# ── Size helpers ─────────────────────────────────────────────────────

def compute_size(quality: str, ratio: str, quality_map: dict) -> str:
    base = quality_map[quality]
    wr, hr = map(int, ratio.split(":"))
    if wr >= hr:
        w, h = base * wr // hr, base
    else:
        w, h = base, base * hr // wr
    return f"{max(64, w // 8 * 8)}x{max(64, h // 8 * 8)}"

def resolve_size(quality: str, ratio: str, quality_map: dict,
                 img_shape: tuple = None) -> str:
    if ratio == "auto" and img_shape is not None:
        _, h, w, _ = img_shape
        base = quality_map[quality]
        if w >= h:
            out_w, out_h = base * w // h, base
        else:
            out_w, out_h = base, base * h // w
        return f"{max(64, out_w // 8 * 8)}x{max(64, out_h // 8 * 8)}"
    if ratio == "auto":
        ratio = "1:1"
    return compute_size(quality, ratio, quality_map)

# ── Video helpers ────────────────────────────────────────────────────

def duration_to_num_frames(duration: int, fps: int) -> int:
    target = duration * fps
    n = max(1, round((target - 1) / 8))
    return min(n * 8 + 1, 441)


def extract_last_frame(video_path: str):
    try:
        import subprocess, tempfile
        from PIL import Image
        # Get total frame count
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-count_frames", "-show_entries", "stream=nb_read_frames",
             "-of", "csv=p=0", video_path],
            capture_output=True, text=True, timeout=30,
        )
        total = int(r.stdout.strip())
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        subprocess.run(
            ["ffmpeg", "-y", "-i", video_path,
             "-vf", f"select='eq(n,{total-1})'",
             "-frames:v", "1", tmp.name],
            capture_output=True, timeout=30,
        )
        img = Image.open(tmp.name).convert("RGB")
        os.unlink(tmp.name)
        return img
    except Exception:
        return None

# ── HTTP helpers ─────────────────────────────────────────────────────

_RETRY_STATUSES = {429, 500, 502, 503, 504, 524}
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 3

def _headers(key: str) -> dict:
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

def _req(method: str, url: str, headers: dict, data: bytes = None,
         timeout: int = 120) -> dict:
    last_err = None
    for attempt in range(1, _MAX_RETRIES + 1):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
            return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            if e.code in _RETRY_STATUSES and attempt < _MAX_RETRIES:
                time.sleep(_RETRY_BASE_DELAY * (2 ** (attempt - 1)))
                last_err = f"API error {e.code}: {body[:200]}"
                continue
            raise RuntimeError(f"API error {e.code}: {body[:500]}")
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_BASE_DELAY * (2 ** (attempt - 1)))
                last_err = str(e)
                continue
            raise RuntimeError(f"Request failed: {e}")
    raise RuntimeError(str(last_err))

# ── Image ────────────────────────────────────────────────────────────

def generate_image(api_key: str, prompt: str, images_b64: list = None,
                   size: str = "1024x768",
                   model: str = "agnes-image-2.1-flash") -> list[str]:
    body = {"model": model, "prompt": prompt, "size": size}
    if images_b64:
        body["extra_body"] = {
            "image": images_b64,
            "response_format": "b64_json",
        }
    data = _req("POST", f"{API_BASE}/images/generations", _headers(api_key),
                data=json.dumps(body).encode(), timeout=300)
    items = data.get("data", [])
    if not items:
        raise RuntimeError("No images returned")
    if "b64_json" in items[0]:
        raw = base64.b64decode(items[0]["b64_json"])
        try:
            from folder_paths import get_temp_directory
            tmpdir = get_temp_directory()
        except ImportError:
            tmpdir = tempfile.gettempdir()
        os.makedirs(tmpdir, exist_ok=True)
        path = os.path.join(tmpdir, f"agnes_img_{int(time.time())}.png")
        with open(path, "wb") as f:
            f.write(raw)
        return [path]
    urls = [item["url"] for item in items if item.get("url")]
    if not urls:
        raise RuntimeError("No images returned")
    return urls

# ── Video ────────────────────────────────────────────────────────────

def create_video(api_key: str, prompt: str, mode: str = "text2video",
                 image_b64: str = None, end_frame_b64: str = None,
                 size: str = None, num_frames: int = 121,
                 frame_rate: int = 24, seed: int = None,
                 output_dir: str = None) -> str:
    body = {"model": "agnes-video-v2.0", "prompt": prompt,
            "num_frames": num_frames, "frame_rate": frame_rate}
    if size:
        parts = size.split("x")
        if len(parts) == 2:
            body["width"] = int(parts[0])
            body["height"] = int(parts[1])
    if seed is not None:
        body["seed"] = seed
    if mode == "img2video" and image_b64:
        body["image"] = image_b64
    elif mode == "keyframes":
        imgs = []
        if image_b64: imgs.append(image_b64)
        if end_frame_b64: imgs.append(end_frame_b64)
        body["extra_body"] = {"image": imgs, "mode": "keyframes"}

    data = _req("POST", f"{API_BASE}/videos", _headers(api_key),
                data=json.dumps(body).encode(), timeout=60)
    vid = data.get("video_id") or data.get("id") or ""
    if not vid:
        raise RuntimeError(f"No video_id: {data}")
    return _poll(api_key, vid, output_dir)

def _poll(api_key: str, video_id: str, output_dir: str = None,
          max_wait: int = 600) -> str:
    url = f"{POLL_BASE}/agnesapi?video_id={video_id}&model_name=agnes-video-v2.0"
    hdrs = _headers(api_key)
    start = time.time()
    while time.time() - start < max_wait:
        time.sleep(10)
        try:
            data = _req("GET", url, hdrs, timeout=30)
        except RuntimeError:
            continue
        st = data.get("status", data.get("state", ""))
        if st == "completed":
            vu = data.get("url") or data.get("video_url") or ""
            if not vu:
                for item in data.get("data", []):
                    vu = item.get("url") or item.get("video_url") or ""
                    if vu: break
            if not vu:
                raise RuntimeError(f"No video URL: {json.dumps(data)[:300]}")
            return _download(vu, output_dir)
        if st in ("failed", "error"):
            raise RuntimeError(f"Video failed: {data.get('error', data.get('message', 'unknown'))}")
    raise TimeoutError(f"Video timed out ({max_wait}s)")

def _download(url: str, output_dir: str = None) -> str:
    if output_dir is None:
        try:
            from folder_paths import get_temp_directory
            output_dir = get_temp_directory()
        except ImportError:
            output_dir = tempfile.gettempdir()
    d = output_dir
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f"agnes_video_{int(time.time())}.mp4")
    try:
        urllib.request.urlretrieve(url, p)
    except Exception as e:
        raise RuntimeError(f"Download failed: {e}")
    return p

# ── Text ─────────────────────────────────────────────────────────────

def chat(api_key: str, messages: list, temperature: float = 0.7,
         max_tokens: int = 2048) -> str:
    body = {
        "model": "agnes-2.0-flash",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    data = _req("POST", f"{API_BASE}/chat/completions", _headers(api_key),
                data=json.dumps(body).encode(), timeout=120)
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise RuntimeError(f"Unexpected response: {data}")
