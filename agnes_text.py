import base64
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


class AgnesText:
    CATEGORY = "🧪AILab/🤖Agnes-AI"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("output",)
    FUNCTION = "process"

    @classmethod
    def INPUT_TYPES(cls):
        styles = get_styles()
        return {
            "required": {
                "api_key": ("STRING", {
                    "default": "", "multiline": False, "placeholder": "sk-...",
                }),
                "style": (list(styles.keys()), {"default": "Prompt Enhance"}),
                "prompt": ("STRING", {
                    "default": "", "multiline": True,
                    "placeholder": "Enter prompt to enhance or translate...",
                }),
            },
            "optional": {
                "system_prompt": ("STRING", {
                    "multiline": True, "default": "",
                    "placeholder": "Custom system prompt (overrides style preset)",
                }),
                "image": ("IMAGE", {
                    "tooltip": "Image input for styles that require it (e.g. Image Detailed Description)",
                }),
            },
        }

    def process(self, api_key="", style="", prompt="", system_prompt="", image=None):
        key = get_api_key(api_key)
        if not key:
            raise ValueError("API key required")

        styles = get_styles()
        style_def = styles.get(style, {})
        sys_prompt = system_prompt.strip() or style_def.get("system_prompt", "")

        if style_def.get("requires_image", False):
            if image is None:
                raise ValueError(f"Image input required for style: {style}")
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
                raise ValueError("Prompt text required for this style")
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": prompt.strip()},
            ]

        result = chat(key, messages, temperature=0.3, max_tokens=2048)
        return (result.strip(),)


NODE_CLASS_MAPPINGS = {"AgnesText": AgnesText}
NODE_DISPLAY_NAME_MAPPINGS = {"AgnesText": "Agnes-AI Text"}
