import json

from agnes_api import _load_config, _parse_keys, _save_config, DEFAULT_STYLES, TEXT_MODELS, IMAGE_MODELS, VIDEO_MODELS


def _mask_key(key: str) -> str:
    if len(key) < 12:
        return "****" if key else ""
    return key[:6] + "****" + key[-4:]


def _is_masked(key: str) -> bool:
    return "****" in key


class AgnesConfig:
    CATEGORY = "🧪AILab/🤖Agnes-AI"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("status",)
    FUNCTION = "apply"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        cfg = _load_config()
        styles_json = json.dumps(cfg.get("prompt_styles", DEFAULT_STYLES), indent=2)
        return {
            "required": {
                "api_key": ("STRING", {
                    "default": _mask_key(cfg.get("api_key", "")),
                    "multiline": False, "placeholder": "sk-... (comma-separated for multiple keys)",
                }),
                "text_model": (TEXT_MODELS, {
                    "default": cfg.get("models", {}).get("text", "agnes-2.0-flash"),
                }),
                "image_model": (IMAGE_MODELS, {
                    "default": cfg.get("models", {}).get("image", "agnes-image-2.1-flash"),
                }),
                "video_model": (VIDEO_MODELS, {
                    "default": cfg.get("models", {}).get("video", "agnes-video-v2.0"),
                }),
                "custom_styles_json": ("STRING", {
                    "default": styles_json,
                    "multiline": True,
                    "placeholder": '{"Style Name": {"system_prompt": "...", "requires_image": false}}',
                }),
            },
        }

    def apply(self, api_key="", text_model="agnes-2.0-flash",
              image_model="agnes-image-2.1-flash", video_model="agnes-video-v2.0",
              custom_styles_json="{}"):
        cfg = _load_config()

        if not _is_masked(api_key):
            cfg["api_key"] = api_key
            cfg["api_key_index"] = 0

        cfg["models"] = {
            "text": text_model,
            "image": image_model,
            "video": video_model,
        }

        try:
            styles = json.loads(custom_styles_json) if custom_styles_json.strip() else {}
        except json.JSONDecodeError as e:
            return (f"Invalid JSON: {e}",)
        if styles:
            cfg["prompt_styles"] = styles
        else:
            cfg.pop("prompt_styles", None)

        _save_config(cfg)

        keys = _parse_keys(cfg.get("api_key", ""))
        return (f"Saved. {len(keys)} key(s) configured.\nText: {text_model}\nImage: {image_model}\nVideo: {video_model}",)


NODE_CLASS_MAPPINGS = {"AgnesConfig": AgnesConfig}
NODE_DISPLAY_NAME_MAPPINGS = {"AgnesConfig": "Agnes-AI Config"}
