import base64, json, os, random, ssl, tempfile, threading, time, uuid
import urllib.error, urllib.request
from io import BytesIO
from pathlib import Path
from PIL import Image

def _get_ssl_ctx():
    if os.environ.get("AGNES_SSL_VERIFY", "").lower() in ("0", "false", "no"):
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return ctx
        except Exception:
            return None

    try:
        import certifi
        ca = certifi.where()
        if ca and os.path.exists(ca):
            return ssl.create_default_context(cafile=ca)
    except Exception:
        pass

    try:
        return ssl.create_default_context()
    except Exception:
        pass
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    except Exception:
        return None

_SSL_CTX = _get_ssl_ctx()

API_BASE = "https://apihub.agnes-ai.com/v1"
POLL_BASE = "https://apihub.agnes-ai.com"
PLUGIN_DIR = Path(__file__).parent
CONFIG_FILE = PLUGIN_DIR / "agnes_config.json"
PRESETS_DIR = PLUGIN_DIR / "presets"
STYLES_FILE = PRESETS_DIR / "styles.json"

def _get_temp_dir() -> str:
    try:
        from folder_paths import get_temp_directory
        return get_temp_directory()
    except ImportError:
        return tempfile.gettempdir()

QUALITY_IMAGE = {"1K": 1024, "2K": 2048, "3K": 3072, "4K": 4096}
ASPECT_RATIOS = [
    "auto", "1:1", "2:3", "3:4", "4:5", "9:16", "9:21",
    "3:2", "4:3", "5:4", "16:9", "21:9",
]
VIDEO_ASPECT_RATIOS = ["auto", "16:9", "9:16", "1:1", "4:3", "3:4", "21:9"]

TEXT_MODELS = [
    "agnes-3.0-flash",
    "agnes-2.5-pro",
    "agnes-2.5-pro-beta",
    "agnes-2.5-flash",
]
IMAGE_MODELS = [
    "agnes-image-2.5-flash",
    "agnes-image-2.1-flash",
    "agnes-image-2.0-flash",
]
VIDEO_MODELS = [
    "agnes-video-2.5-flash",
    "agnes-video-2.5",
    "agnes-video-v2.0",
]


# ── Config ───────────────────────────────────────────────────────────

def load_config() -> dict:
    try:
        if CONFIG_FILE.exists():
            text = CONFIG_FILE.read_text(encoding="utf-8")
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                import re
                clean = re.sub(r",\s*([\]}])", r"\1", text)
                try:
                    return json.loads(clean)
                except json.JSONDecodeError:
                    print(f"[Agnes-AI] WARNING: Config file {CONFIG_FILE} is corrupted. Using defaults.")
    except OSError as e:
        print(f"[Agnes-AI] WARNING: Cannot read config file: {e}")
    return {}

def save_config(cfg: dict) -> bool:
    try:
        tmp = CONFIG_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(CONFIG_FILE)
        return True
    except OSError as e:
        print(f"[Agnes-AI] WARNING: Failed to save config: {e}")
        return False

_load_config = load_config
_save_config = save_config

MAX_IMAGE_SIZE = 50 * 1024 * 1024  # 50MB

def download_image(url: str) -> Image.Image:
    """Download image from URL using SSL context and return PIL Image."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    kwargs = {"timeout": 120}
    if _SSL_CTX is not None:
        kwargs["context"] = _SSL_CTX
    with urllib.request.urlopen(req, **kwargs) as resp:
        data = resp.read(MAX_IMAGE_SIZE + 1)
        if len(data) > MAX_IMAGE_SIZE:
            raise RuntimeError(f"Image exceeds {MAX_IMAGE_SIZE // (1024 * 1024)}MB limit")
        return Image.open(BytesIO(data)).convert("RGB")

def _parse_keys(raw) -> list[str]:
    if isinstance(raw, list):
        return [str(k).strip() for k in raw if str(k).strip()]
    if isinstance(raw, str):
        return [k.strip() for k in raw.replace(";", ",").replace("\n", ",").split(",") if k.strip()]
    return []

def get_all_keys() -> list[str]:
    env = os.environ.get("AGNES_API_KEY") or os.environ.get("AGNES_API_TOKEN") or ""
    if env:
        return _parse_keys(env)
    cfg = load_config()
    return _parse_keys(cfg.get("api_keys") or cfg.get("api_key") or "")

_key_lock = threading.Lock()
_KEY_COOLDOWNS: dict[str, float] = {}

def mark_key_cooldown(key: str, seconds: int = 120):
    if key:
        with _key_lock:
            _KEY_COOLDOWNS[key] = time.time() + seconds

def get_api_key_info(node_name: str = "", exclude_key: str = "") -> tuple[str, str]:
    keys = get_all_keys()
    if not keys:
        return "", ""
    if len(keys) == 1:
        prefix = f"[{node_name}] " if node_name else ""
        print(f"[Agnes-AI] {prefix}Using API 0")
        return keys[0], "API 0"

    now = time.time()
    with _key_lock:
        available = [
            (i, k) for i, k in enumerate(keys)
            if _KEY_COOLDOWNS.get(k, 0) <= now and k != exclude_key
        ]
        if not available and exclude_key:
            available = [
                (i, k) for i, k in enumerate(keys)
                if _KEY_COOLDOWNS.get(k, 0) <= now
            ]
        if not available:
            available = list(enumerate(keys))

        chosen_idx, chosen_key = random.choice(available)

    label = f"API {chosen_idx} ({chosen_idx + 1}/{len(keys)})"
    prefix = f"[{node_name}] " if node_name else ""
    print(f"[Agnes-AI] {prefix}Using {label}")
    return chosen_key, label

def get_api_key(node_name: str = "") -> str:
    key, _ = get_api_key_info(node_name=node_name)
    return key

def get_model(model_type: str, widget_model: str = "") -> str:
    if widget_model.strip():
        return widget_model.strip()
    if model_type == "chat":
        model_type = "text"
    cfg = _load_config()
    model = cfg.get("models", {}).get(model_type, "")
    valid_map = {
        "image": IMAGE_MODELS,
        "video": VIDEO_MODELS,
        "text": TEXT_MODELS,
    }
    valid = valid_map.get(model_type, [])
    if model in valid:
        return model
    return _default_model(model_type)

def _default_model(model_type: str) -> str:
    if model_type == "chat":
        model_type = "text"
    models = {
        "image": IMAGE_MODELS,
        "video": VIDEO_MODELS,
        "text": TEXT_MODELS,
    }.get(model_type, [])
    return models[0] if models else ""

_styles_cache = None
_styles_mtime = 0

def get_styles() -> dict:
    global _styles_cache, _styles_mtime
    try:
        current_mtime = max(
            STYLES_FILE.stat().st_mtime if STYLES_FILE.exists() else 0,
            CONFIG_FILE.stat().st_mtime if CONFIG_FILE.exists() else 0,
        )
    except OSError:
        current_mtime = 0

    if _styles_cache is not None and current_mtime > 0 and current_mtime <= _styles_mtime:
        return _styles_cache

    styles = {}

    if STYLES_FILE.exists():
        try:
            text = STYLES_FILE.read_text(encoding="utf-8")
            data = json.loads(text)
            if isinstance(data, dict):
                styles.update(data)
        except Exception as e:
            print(f"[Agnes-AI] Error loading {STYLES_FILE}: {e}")

    if PRESETS_DIR.exists():
        for p in sorted(PRESETS_DIR.iterdir()):
            if p.name == "styles.json" or p.name.startswith("."):
                continue
            if p.suffix.lower() == ".json":
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        if "system_prompt" in data:
                            name = data.get("name", p.stem)
                            styles[name] = data
                        else:
                            styles.update(data)
                except Exception as e:
                    print(f"[Agnes-AI] Error loading preset file {p.name}: {e}")
            elif p.suffix.lower() == ".md":
                try:
                    content = p.read_text(encoding="utf-8").strip()
                    if content:
                        styles[p.stem] = {
                            "system_prompt": content,
                            "requires_image": False,
                        }
                except Exception as e:
                    print(f"[Agnes-AI] Error loading markdown preset {p.name}: {e}")

    cfg = _load_config()
    saved = cfg.get("prompt_styles")
    if saved and isinstance(saved, dict):
        styles.update(saved)
    if not styles:
        styles = {
            "Prompt Enhance": {
                "system_prompt": (
                    "You are an expert prompt engineer for AI image generation. Expand and enrich "
                    "the given prompt with vivid visual context: subject details, lighting, color palette, "
                    "composition, mood, camera angle, and style. Output ONLY the expanded prompt text. "
                    "Do NOT include any title, prefix, preamble, or labels such as 'Prompt:' or '**Prompt:**'."
                ),
                "requires_image": False,
            }
        }

    _styles_cache = styles
    _styles_mtime = current_mtime
    return styles

# ── Size helpers ─────────────────────────────────────────────────────

def compute_size(quality: str, ratio: str, quality_map: dict) -> str:
    if quality not in quality_map:
        quality = next(iter(quality_map)) if quality_map else "1K"
    base = quality_map.get(quality, 1024)
    parts = str(ratio).split(":")
    if len(parts) != 2:
        return f"{base}x{base}"
    try:
        wr, hr = int(parts[0]), int(parts[1])
    except (ValueError, TypeError):
        return f"{base}x{base}"
    if wr <= 0 or hr <= 0:
        return f"{base}x{base}"
    if wr >= hr:
        w, h = base * wr // hr, base
    else:
        w, h = base, base * hr // wr
    return f"{max(64, w // 8 * 8)}x{max(64, h // 8 * 8)}"

def resolve_size(quality: str, ratio: str, quality_map: dict,
                 img_shape: tuple = None) -> str:
    if ratio == "auto":
        ratio = f"{img_shape[2]}:{img_shape[1]}" if img_shape is not None else "1:1"
    return compute_size(quality, ratio, quality_map)

def resolve_video_aspect_ratio(aspect_ratio: str, img_shape: tuple = None) -> str:
    valid_ratios = ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"]
    if aspect_ratio in valid_ratios:
        return aspect_ratio
    if aspect_ratio == "auto" and img_shape is not None:
        _, h, w, _ = img_shape
        ratio_val = w / max(1, h)
        candidates = {
            "21:9": 21 / 9,
            "16:9": 16 / 9,
            "4:3": 4 / 3,
            "1:1": 1.0,
            "3:4": 3 / 4,
            "9:16": 9 / 16,
        }
        return min(candidates.keys(), key=lambda r: abs(candidates[r] - ratio_val))
    return "16:9"


def extract_input_items(kwargs: dict, group_id: str, prefix: str) -> list:
    items = []
    if group_id in kwargs and kwargs[group_id] is not None:
        val = kwargs[group_id]
        if isinstance(val, dict):
            for k in sorted(val.keys()):
                if val[k] is not None:
                    items.append(val[k])
        elif isinstance(val, (list, tuple)):
            for item in val:
                if item is not None:
                    items.append(item)
        else:
            items.append(val)
    for k in sorted(kwargs.keys()):
        if k == group_id:
            continue
        if k.startswith(prefix) or k.startswith(f"{group_id}.{prefix}"):
            if kwargs[k] is not None:
                items.append(kwargs[k])
    return items

# ── HTTP helpers ─────────────────────────────────────────────────────

_ERR_HINTS = {
    400: "Invalid request parameters or unsupported format.",
    401: "Invalid or expired API key. Check ComfyUI Settings -> Agnes-AI.",
    402: "Insufficient account balance or subscription quota.",
    404: "Endpoint, model, or task not found.",
    429: "API rate limit or quota exceeded.",
}

def _abort_execution(msg: str):
    """Print preset error message and cleanly interrupt execution without Python traceback."""
    print(f"[Agnes-AI] {msg}")
    try:
        import comfy.model_management
        raise comfy.model_management.InterruptProcessingException()
    except (ImportError, AttributeError):
        raise RuntimeError(f"[Agnes-AI] {msg}") from None

def _headers(key: str) -> dict:
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

def _req(method: str, url: str, headers: dict, data: bytes = None, timeout: int = 120) -> dict:
    keys = get_all_keys()
    max_attempts = max(3, len(keys) * 2)

    for attempt in range(max_attempts):
        curr_key = headers.get("Authorization", "").replace("Bearer ", "").strip()
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            kwargs = {"timeout": timeout}
            if _SSL_CTX is not None:
                kwargs["context"] = _SSL_CTX
            resp = urllib.request.urlopen(req, **kwargs)
            return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            detail = ""
            try:
                err_json = json.loads(body)
                detail = err_json.get("detail") or err_json.get("message") or err_json.get("error", "")
                if isinstance(detail, dict):
                    detail = detail.get("message", str(detail))
            except Exception:
                detail = body[:150]

            if len(keys) > 1 and attempt < max_attempts - 1 and e.code in (401, 402, 429, 500, 502, 503, 504):
                cooldown_sec = 180 if e.code in (401, 402) else (120 if e.code == 429 else 30)
                mark_key_cooldown(curr_key, seconds=cooldown_sec)
                next_key, next_label = get_api_key_info("Failover", exclude_key=curr_key)
                if next_key and next_key != curr_key:
                    headers["Authorization"] = f"Bearer {next_key}"
                    print(f"[Agnes-AI] Error {e.code} on current key. Switching to {next_label}...")
                    time.sleep(0.5)
                    continue

            if e.code in (502, 504) and attempt < max_attempts - 1:
                backoff = min(2 ** attempt, 8)
                print(f"[Agnes-AI] Server error ({e.code}). Retrying in {backoff}s (attempt {attempt + 1}/{max_attempts})...")
                time.sleep(backoff)
                continue

            hint = _ERR_HINTS.get(e.code) or ("Server temporarily unavailable." if e.code >= 500 else f"HTTP error {e.code}.")
            msg = f"{hint} ({detail})" if detail else hint
            _abort_execution(f"Error {e.code}: {msg}")
        except (urllib.error.URLError, TimeoutError) as e:
            if len(keys) > 1 and attempt < max_attempts - 1:
                mark_key_cooldown(curr_key, seconds=30)
                next_key, next_label = get_api_key_info("Failover", exclude_key=curr_key)
                if next_key and next_key != curr_key:
                    headers["Authorization"] = f"Bearer {next_key}"
                    print(f"[Agnes-AI] Network error on current key. Switching to {next_label}...")
                    time.sleep(0.5)
                    continue
            if attempt < max_attempts - 1:
                backoff = min(2 ** attempt, 8)
                print(f"[Agnes-AI] Network error ({e}). Retrying in {backoff}s (attempt {attempt + 1}/{max_attempts})...")
                time.sleep(backoff)
                continue
            _abort_execution(f"Network error: {e}")
        except json.JSONDecodeError as e:
            _abort_execution(f"Invalid JSON response: {e}")

    _abort_execution("All API key attempts failed.")

# ── Image ────────────────────────────────────────────────────────────

def generate_image(api_key: str, prompt: str, images_b64: list = None,
                   size: str = "1024x768",
                   seed: int = None,
                   model: str = "") -> list[str]:
    selected_model = get_model("image", model)
    body = {"model": selected_model, "prompt": prompt, "size": size}
    if seed is not None and seed > 0:
        body["seed"] = seed % 1000
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
    first = items[0]
    if not first.get("url") and not first.get("b64_json"):
        raise RuntimeError(f"Unexpected API response: {json.dumps(first)[:200]}")
    if first.get("b64_json"):
        raw = base64.b64decode(first["b64_json"])
        tmpdir = _get_temp_dir()
        os.makedirs(tmpdir, exist_ok=True)
        path = os.path.join(tmpdir, f"agnes_img_{uuid.uuid4().hex[:12]}.png")
        with open(path, "wb") as f:
            f.write(raw)
        return [path]
    urls = [item["url"] for item in items if item.get("url")]
    if not urls:
        raise RuntimeError("No images returned")
    return urls

# ── Video ────────────────────────────────────────────────────────────

_V2_DIMS = {
    "16:9": {"480p": (848, 480), "720p": (1280, 720), "1080p": (1920, 1080)},
    "9:16": {"480p": (480, 848), "720p": (720, 1280), "1080p": (1080, 1920)},
    "1:1":  {"480p": (480, 480), "720p": (720, 720),  "1080p": (1080, 1080)},
    "4:3":  {"480p": (640, 480), "720p": (960, 720),  "1080p": (1440, 1080)},
    "3:4":  {"480p": (480, 640), "720p": (720, 960),  "1080p": (1080, 1440)},
    "21:9": {"480p": (1120, 480), "720p": (1680, 720), "1080p": (2520, 1080)},
}

def create_video(api_key: str, prompt: str, mode: str = "text",
                 first_frame_b64: str = None, end_frame_b64: str = None,
                 images_b64: list = None, audios_b64: list = None,
                 videos_payload: list = None,
                 quality: str = "720P",
                 aspect_ratio: str = "16:9", seconds: int = 5,
                 seed: int = None, model: str = "",
                 output_dir: str = None) -> str:
    selected_model = get_model("video", model)
    is_flash = "flash" in selected_model.lower()
    p = (prompt or "").strip()
    if not p:
        if mode == "keyframe":
            p = "Animate with natural, smooth cinematic motion"
        elif mode == "reference":
            p = "Generate a cinematic video based on the reference materials"
        else:
            p = "Cinematic video with natural movement and lighting"

    if "v2.0" in selected_model:
        num_frames = max(1, round(((int(seconds) * 24) - 1) / 8)) * 8 + 1
        q_norm = str(quality).lower().strip()
        if q_norm in ("1k", "2k"):
            q_norm = "1080p"
        if q_norm not in ("480p", "720p", "1080p"):
            q_norm = "720p"
        ratio_key = aspect_ratio if aspect_ratio in _V2_DIMS else "16:9"
        w, h = _V2_DIMS[ratio_key][q_norm]
        body = {
            "model": selected_model,
            "prompt": p,
            "num_frames": num_frames,
            "frame_rate": 24,
            "width": w,
            "height": h,
        }
        if seed is not None and seed > 0:
            body["seed"] = seed % 2147483647
        if mode == "keyframe":
            if first_frame_b64 and end_frame_b64:
                body["extra_body"] = {"image": [first_frame_b64, end_frame_b64], "mode": "keyframes"}
            elif first_frame_b64:
                body["image"] = first_frame_b64
        elif mode == "reference":
            if images_b64:
                body["extra_body"] = {"image": images_b64, "mode": "keyframes"}
    else:
        sec_int = max(4, min(12, int(seconds)))
        final_size = "720P"
        if is_flash:
            if str(quality).upper() != "720P":
                print(f"[Agnes-AI] Official API constraint: Flash model only supports 720P. Auto-downgraded from '{quality}' to 720P to prevent HTTP 400 error.")
            final_size = "720P"
            if videos_payload:
                print("[Agnes-AI] Official API constraint: Flash model does not support reference videos (videos is not supported). Reference video skipped to prevent HTTP 400. Switch to standard agnes-video-2.5 in Settings to use video reference.")
                videos_payload = None
        else:
            final_size = str(quality).upper().strip()
            if final_size == "480P":
                print("[Agnes-AI] Note: agnes-video-2.5 standard model minimum resolution is 720P. Auto-adjusting to 720P.")
                final_size = "720P"
            elif final_size not in ("720P", "1080P", "1K", "2K"):
                final_size = "720P"

        body = {
            "model": selected_model,
            "prompt": p,
            "mode": mode,
            "seconds": str(sec_int),
            "size": final_size,
            "aspect_ratio": aspect_ratio,
            "n": 1,
        }
        if seed is not None and seed > 0:
            body["seed"] = seed % 2147483647

        if mode == "keyframe":
            if first_frame_b64:
                body["first_frame"] = first_frame_b64
            if end_frame_b64:
                body["last_frame"] = end_frame_b64
        elif mode == "reference":
            if images_b64:
                body["images"] = images_b64[:5]
            if audios_b64:
                body["audios"] = audios_b64[:3]
            if videos_payload:
                body["videos"] = videos_payload[:3]

    data = _req("POST", f"{API_BASE}/videos", _headers(api_key),
                data=json.dumps(body).encode(), timeout=60)
    vid = data.get("video_id") or data.get("id") or ""
    if not vid:
        raise RuntimeError(f"[Agnes-AI] No video_id returned: {data}")
    return _poll(api_key, vid, model_name=selected_model, output_dir=output_dir)

def _poll(api_key: str, video_id: str, model_name: str = "",
          output_dir: str = None, max_wait: int = 600) -> str:
    target_model = model_name or _default_model("video")
    url = f"{POLL_BASE}/agnesapi?video_id={video_id}&model_name={target_model}"
    hdrs = _headers(api_key)
    start = time.time()

    pbar = None
    try:
        import comfy.utils
        pbar = comfy.utils.ProgressBar(100)
    except Exception:
        pass

    check_interrupt = None
    try:
        import comfy.model_management
        check_interrupt = comfy.model_management.throw_exception_if_processing_interrupted
    except Exception:
        pass

    while time.time() - start < max_wait:
        if check_interrupt:
            check_interrupt()
        for _ in range(10):
            time.sleep(1)
            if check_interrupt:
                check_interrupt()
        try:
            req = urllib.request.Request(url, headers=_headers(api_key))
            kwargs = {"timeout": 30}
            if _SSL_CTX is not None:
                kwargs["context"] = _SSL_CTX
            with urllib.request.urlopen(req, **kwargs) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 404):
                _abort_execution(f"Video poll failed: HTTP {e.code} — {e.read().decode()[:200]}")
            print(f"[Agnes-AI] Poll request failed (HTTP {e.code}), retrying...")
            continue
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
            print(f"[Agnes-AI] Poll request failed ({e}), retrying...")
            continue

        progress = data.get("progress")
        if progress is not None and pbar is not None:
            pbar.update_absolute(min(100, max(0, int(progress))))

        st = data.get("status", data.get("state", ""))
        if st == "completed":
            if pbar is not None:
                pbar.update_absolute(100)
            vu = data.get("url") or data.get("video_url") or ""
            if not vu:
                meta = data.get("metadata", {})
                if isinstance(meta, dict):
                    vu = meta.get("url") or meta.get("video_url") or ""
            if not vu:
                for item in data.get("data", []):
                    vu = item.get("url") or item.get("video_url") or ""
                    if vu: break
            if not vu:
                _abort_execution(f"No video URL in completed response: {json.dumps(data)[:300]}")
            return _download(vu, output_dir)
        if st in ("failed", "error"):
            err_msg = data.get("error", data.get("message", "unknown"))
            if isinstance(err_msg, dict):
                err_msg = err_msg.get("message", str(err_msg))
            _abort_execution(f"Video generation failed: {err_msg}")

    _abort_execution(f"Video generation timed out ({max_wait}s)")

def _download(url: str, output_dir: str = None) -> str:
    d = output_dir or _get_temp_dir()
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f"agnes_video_{uuid.uuid4().hex[:12]}.mp4")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        kwargs = {"timeout": 120}
        if _SSL_CTX is not None:
            kwargs["context"] = _SSL_CTX
        with urllib.request.urlopen(req, **kwargs) as resp, open(p, "wb") as f:
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                f.write(chunk)
    except Exception as e:
        raise RuntimeError(f"Download failed: {e}")
    return p

# ── Text ─────────────────────────────────────────────────────────────

def chat(api_key: str, messages: list, temperature: float = 0.7,
         max_tokens: int = 2048, seed: int = None, model: str = "") -> str:
    selected_model = get_model("text", model)
    body = {
        "model": selected_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if seed is not None and seed > 0:
        body["seed"] = seed % 2147483647
    data = _req("POST", f"{API_BASE}/chat/completions", _headers(api_key),
                data=json.dumps(body).encode(), timeout=120)
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise RuntimeError(f"Unexpected response: {data}")
