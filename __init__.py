import importlib.util, json, logging, os, sys

from aiohttp import web
import server

# ── Logging ──────────────────────────────────────────────────────────
logger = logging.getLogger("AgnesAI")

# ── Tell ComfyUI to serve our frontend JS ────────────────────────────
WEB_DIRECTORY = "web"

# ── Node discovery ───────────────────────────────────────────────────
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

def _load_nodes():
    current_dir = os.path.dirname(__file__)
    sys.path.insert(0, current_dir)
    for f in sorted(os.listdir(current_dir)):
        if f == "__init__.py" or not f.endswith(".py"):
            continue
        name = f[:-3]
        spec = importlib.util.spec_from_file_location(name, os.path.join(current_dir, f))
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "NODE_CLASS_MAPPINGS"):
                NODE_CLASS_MAPPINGS.update(mod.NODE_CLASS_MAPPINGS)
            if hasattr(mod, "NODE_DISPLAY_NAME_MAPPINGS"):
                NODE_DISPLAY_NAME_MAPPINGS.update(mod.NODE_DISPLAY_NAME_MAPPINGS)

_load_nodes()

# ── Config helpers (reuse from agnes_api) ────────────────────────────
PLUGIN_DIR = os.path.dirname(__file__)
CONFIG_FILE = os.path.join(PLUGIN_DIR, "agnes_config.json")

def _load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
    return {}

def _save_config(config: dict) -> bool:
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        return False

def _mask_key(key: str) -> str:
    """Mask API key for display: show first 6 + last 4 chars."""
    if not key:
        return ""
    if len(key) < 12:
        return "****"
    return key[:6] + "****" + key[-4:]

# ── HTTP API routes ──────────────────────────────────────────────────

@server.PromptServer.instance.routes.post("/agnes/save_config")
async def save_config(request):
    """Save config from the Settings Panel."""
    try:
        data = await request.json()
        cfg = _load_config()

        # API Key — only update if provided and not masked
        api_key = data.get("api_key", "")
        if api_key and "****" not in api_key:
            cfg["api_key"] = api_key
            cfg["api_key_index"] = 0

        # Models — update if provided
        models = {}
        for key in ("text", "image", "video"):
            model_key = f"{key}_model"
            if model_key in data and data[model_key]:
                models[key] = data[model_key]
        if models:
            cfg.setdefault("models", {}).update(models)

        if _save_config(cfg):
            logger.info("Config saved via Settings Panel")
            return web.json_response({"status": "success", "message": "Config saved"})
        else:
            return web.json_response(
                {"status": "error", "message": "Failed to save — check plugin directory permissions"},
                status=500,
            )
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return web.json_response(
            {"status": "error", "message": f"Server error: {str(e)}"},
            status=500,
        )

@server.PromptServer.instance.routes.get("/agnes/get_config")
async def get_config(request):
    """Return current config for the Settings Panel (API key masked)."""
    cfg = _load_config()
    models = cfg.get("models", {})
    return web.json_response({
        "has_api_key": bool(cfg.get("api_key")),
        "api_key_masked": _mask_key(cfg.get("api_key", "")),
        "text_model": models.get("text", "agnes-2.5-flash"),
        "image_model": models.get("image", "agnes-image-2.1-flash"),
        "video_model": models.get("video", "agnes-video-v2.0"),
    })

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
