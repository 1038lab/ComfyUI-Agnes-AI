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
    img.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"


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

    def process(self, preset="", prompt="", system_prompt="", image=None):
        key = get_api_key()
        if not key:
            return ("API key required — set it in ComfyUI Settings Panel → Agnes-AI",)

        styles = get_styles()
        style_def = styles.get(preset, {})
        sys_prompt = system_prompt.strip() or style_def.get("system_prompt", "")

        if style_def.get("requires_image", False):
            if image is None:
                return ("Image required for this mode",)
            pil = _tensor_to_pil(image)
            messages = [
                {"role": "system", "content": sys_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": _pil_to_b64_uri(pil)}},
                        {"type": "text", "text": "Describe this image as an AI image generation prompt."},
                    ],
                },
            ]
        else:
            if not prompt.strip():
                return ("Prompt text required for this preset",)
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": prompt.strip()},
            ]

        try:
            result = chat(key, messages, temperature=0.3, max_tokens=2048)
            return (_clean_prompt_output(result),)
        except Exception as e:
            return (f"Error: {str(e)}",)


NODE_CLASS_MAPPINGS = {"AgnesText": AgnesText}
NODE_DISPLAY_NAME_MAPPINGS = {"AgnesText": "Agnes-AI Text"}
