import importlib
import logging
import pkgutil
import sys
from pathlib import Path

from aiohttp import web
import server

__repo_name__ = "ComfyUI-Agnes-AI"
__version__ = "1.2.1"

logger = logging.getLogger("AgnesAI")

# Locate current directory
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# Initialize node mappings
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
WEB_DIRECTORY = "./web"


def load_nodes():
    """Automatically discover and load node definitions."""
    for (_, module_name, _) in pkgutil.iter_modules([str(current_dir)]):
        if module_name.startswith("__") or module_name == "agnes_api":
            continue
        try:
            rel_import = f".{module_name}" if __package__ else module_name
            module = importlib.import_module(rel_import, package=__package__)
            if hasattr(module, "NODE_CLASS_MAPPINGS"):
                NODE_CLASS_MAPPINGS.update(module.NODE_CLASS_MAPPINGS)
            if hasattr(module, "NODE_DISPLAY_NAME_MAPPINGS"):
                NODE_DISPLAY_NAME_MAPPINGS.update(module.NODE_DISPLAY_NAME_MAPPINGS)
        except Exception as e:
            print(f"[{__repo_name__}] Error loading {module_name}: {e}")


# Load all nodes
load_nodes()

from agnes_api import load_config as _load_config, save_config as _save_config, _default_model


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) < 12:
        return "****"
    return key[:6] + "****" + key[-4:]

def _mask_keys(raw) -> str:
    if not raw:
        return ""
    if isinstance(raw, list):
        keys = [str(k).strip() for k in raw if str(k).strip()]
    elif isinstance(raw, str):
        keys = [k.strip() for k in raw.replace(";", "\n").replace(",", "\n").split("\n") if k.strip()]
    else:
        keys = []
    if not keys:
        return ""
    return "\n".join(_mask_key(k) for k in keys)

def _resolve_saved_keys(input_str: str, existing_raw) -> any:
    is_list = isinstance(existing_raw, list)
    if is_list:
        existing_keys = [str(k).strip() for k in existing_raw if str(k).strip()]
    elif isinstance(existing_raw, str):
        existing_keys = [k.strip() for k in existing_raw.replace(";", "\n").replace(",", "\n").split("\n") if k.strip()]
    else:
        existing_keys = []

    input_tokens = [k.strip() for k in str(input_str).replace(";", "\n").replace(",", "\n").split("\n") if k.strip()]
    resolved = []
    for token in input_tokens:
        if "****" in token:
            matched = None
            for ek in existing_keys:
                if (
                    len(ek) >= 10
                    and len(token) >= 10
                    and token.startswith(ek[:6])
                    and token.endswith(ek[-4:])
                    and "****" in token[6:-4]
                ):
                    matched = ek
                    break
            if matched and matched not in resolved:
                resolved.append(matched)
        else:
            if token not in resolved:
                resolved.append(token)

    if is_list:
        return resolved
    return ",".join(resolved)


# ── HTTP API routes ──────────────────────────────────────────────────
server_instance = getattr(getattr(server, "PromptServer", None), "instance", None)
if server_instance:
    @server_instance.routes.post("/agnes/save_config")
    async def save_config(request):
        try:
            data = await request.json()
            cfg = _load_config()
            raw_key = cfg.get("api_key", [])
            is_list = isinstance(raw_key, list)
            if is_list:
                keys = [str(k).strip() for k in raw_key if str(k).strip()]
            elif isinstance(raw_key, str):
                keys = [k.strip() for k in raw_key.replace(";", ",").replace("\n", ",").split(",") if k.strip()]
            else:
                keys = []

            # 1. Deletion: ONLY permitted when the user explicitly clicks delete in the Settings Panel
            if "delete_index" in data:
                try:
                    idx = int(data["delete_index"])
                    if 0 <= idx < len(keys):
                        keys.pop(idx)
                        cfg["api_key"] = keys if is_list else ",".join(keys)
                except (ValueError, TypeError):
                    pass

            # 2. Addition: Append-only
            if "add_key" in data:
                add_str = str(data["add_key"]).strip()
                if add_str:
                    new_tokens = [k.strip() for k in add_str.replace(";", ",").replace("\n", ",").split(",") if k.strip()]
                    for nt in new_tokens:
                        if nt and nt not in keys:
                            keys.append(nt)
                    cfg["api_key"] = keys if is_list else ",".join(keys)

            # 3. Initial key setup when NO keys exist at all
            if not keys and "api_key" in data:
                raw_input = data.get("api_key")
                if isinstance(raw_input, str):
                    val = raw_input.strip()
                    if val and not val.startswith("****"):
                        cfg["api_key"] = [val] if is_list else val
                elif isinstance(raw_input, list):
                    cfg["api_key"] = [str(k).strip() for k in raw_input if str(k).strip() and not str(k).strip().startswith("****")]

            cfg.pop("api_key_index", None)

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

    @server_instance.routes.get("/agnes/get_config")
    async def get_config(request):
        cfg = _load_config()
        models = cfg.get("models", {})
        raw_key = cfg.get("api_key", [])
        if isinstance(raw_key, list):
            keys = [str(k).strip() for k in raw_key if str(k).strip()]
        elif isinstance(raw_key, str):
            keys = [k.strip() for k in raw_key.replace(";", ",").replace("\n", ",").split(",") if k.strip()]
        else:
            keys = []
        masked_keys = [_mask_key(k) for k in keys]
        return web.json_response({
            "has_api_key": bool(keys),
            "api_keys": masked_keys,
            "api_key_masked": "\n".join(masked_keys),
            "text_model": models.get("text") or _default_model("text"),
            "image_model": models.get("image") or _default_model("image"),
            "video_model": models.get("video") or _default_model("video"),
        })


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

print(f'\033[36m[{__repo_name__}]\033[0m v'
      f'\033[93m{__version__}\033[0m | '
      f'\033[37m{len(NODE_CLASS_MAPPINGS)} nodes\033[0m '
      f'\033[92mLoaded\033[0m')
