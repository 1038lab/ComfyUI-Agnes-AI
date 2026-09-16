import base64
import re
from io import BytesIO
from PIL import Image
import numpy as np

from agnes_api import get_api_key, get_styles, chat


def _tensor_to_pil(tensor) -> Image.Image:
    i = tensor[0].cpu().numpy()
    return Image.fromarray((i * 255).astype(np.uint8))


def _pil_to_b64_uri(img: Image.Image) -> str:
    buf = BytesIO()
    try:
        img.save(buf, format="PNG")
        return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"
    finally:
        buf.close()


def _clean_prompt_output(text: str) -> str:
    text = text.strip()
    patterns = [
        r"^\*\*prompt:\*\*\s*",
        r"^prompt:\s*",
        r"^\*\*enhanced prompt:\*\*\s*",
        r"^enhanced prompt:\s*",
        r"^\*\*output:\*\*\s*",
        r"^output:\s*",
    ]
    for pat in patterns:
        text = re.sub(pat, "", text, flags=re.IGNORECASE)
    return text.strip()


class AgnesText:
    CATEGORY = "🧪AILab/⚡Agnes-AI"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("output",)
    FUNCTION = "process"
    SEARCH_ALIASES = [
        "agnes", "prompt", "prompt enhance", "translate", "describe image",
        "reverse prompt", "art style", "llm", "chat",
    ]

    @classmethod
    def INPUT_TYPES(cls):
        styles = get_styles()
        return {
            "required": {
                "preset": (list(styles.keys()), {"default": "Prompt Enhance"}),
                "prompt": ("STRING", {
                    "default": "", "multiline": True,
                    "placeholder": "Enter prompt to enhance or translate...",
                }),
                "seed": ("INT", {
                    "default": 0, "min": 0, "max": 0xffffffffffffffff, "step": 1,
                    "control_after_generate": True,
                    "tooltip": "Random seed (0 = random)",
                }),
            },
            "optional": {
                "system_prompt": ("STRING", {
                    "multiline": True, "default": "",
                    "placeholder": "Custom system prompt (overrides preset)",
                }),
                "image": ("IMAGE", {
                    "tooltip": "Image input for presets that require it (e.g. Image Detailed Description)",
                }),
            },
        }

    def process(self, preset="", prompt="", seed=0, system_prompt="", image=None):
        key = get_api_key("AgnesText")
        if not key:
            raise ValueError("API key required — set it in ComfyUI Settings Panel → Agnes-AI")

        try:
            actual_seed = int(seed) if seed is not None and str(seed).strip() else 0
        except (ValueError, TypeError):
            actual_seed = 0

        styles = get_styles()
        if preset not in styles:
            preset = "Prompt Enhance"
        style_def = styles.get(preset, {})
        sys_prompt = system_prompt.strip() or style_def.get("system_prompt", "")

        requires_img = style_def.get("requires_image", False)
        default_user_text = style_def.get("default_prompt", "Describe this image.")
        user_text = prompt.strip() or default_user_text

        if requires_img:
            if image is None:
                raise ValueError("Image required for this mode")
            pil = _tensor_to_pil(image)
            messages = [
                {"role": "system", "content": sys_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": _pil_to_b64_uri(pil)}},
                        {"type": "text", "text": user_text},
                    ],
                },
            ]
        else:
            if image is not None:
                pil = _tensor_to_pil(image)
                user_content = [
                    {"type": "image_url", "image_url": {"url": _pil_to_b64_uri(pil)}},
                ]
                if user_text:
                    user_content.append({"type": "text", "text": user_text})
                messages = [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_content},
                ]
            else:
                if not prompt.strip():
                    raise ValueError("Prompt text required for this preset")
                messages = [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": prompt.strip()},
                ]

        result = chat(key, messages, temperature=0.3, max_tokens=2048, seed=actual_seed)
        return (_clean_prompt_output(result),)


NODE_CLASS_MAPPINGS = {"AgnesText": AgnesText}
NODE_DISPLAY_NAME_MAPPINGS = {"AgnesText": "Agnes-AI Text"}
