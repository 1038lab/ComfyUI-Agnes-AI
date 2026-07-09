import base64, torch
from io import BytesIO
from PIL import Image
import numpy as np

from agnes_api import (
    get_api_key, generate_image, resolve_size,
    QUALITY_IMAGE, ASPECT_RATIOS,
)


def _pil_to_b64(img: Image.Image) -> str:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _tensor_to_pil(tensor, index=0) -> Image.Image:
    i = tensor[index].cpu().numpy()
    return Image.fromarray((i * 255).astype(np.uint8))


def _pil_to_tensor(img: Image.Image):
    a = np.array(img.convert("RGB"), dtype=np.float32) / 255.0
    return torch.from_numpy(a).unsqueeze(0)


class AgnesImage:
    CATEGORY = "🧪AILab/🤖Agnes-AI"
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "generate"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {
                    "default": "", "multiline": False, "placeholder": "sk-...",
                }),
                "prompt": ("STRING", {
                    "default": "", "multiline": True,
                    "placeholder": "Optional when images are connected",
                }),
                "quality": (list(QUALITY_IMAGE.keys()), {"default": "1K"}),
                "aspect_ratio": (ASPECT_RATIOS, {"default": "auto"}),
            },
            "optional": {
                "image": ("IMAGE", {
                    "tooltip": "Primary reference image",
                }),
                "image_2": ("IMAGE", {
                    "tooltip": "Additional reference image",
                }),
                "image_3": ("IMAGE", {
                    "tooltip": "Additional reference image",
                }),
                "image_4": ("IMAGE", {
                    "tooltip": "Additional reference image",
                }),
            },
        }

    def generate(self, api_key="", prompt="", quality="1K",
                 aspect_ratio="auto", image=None, image_2=None, image_3=None,
                 image_4=None):
        key = get_api_key(api_key)
        if not key:
            raise ValueError("API key required")

        has_images = any(x is not None for x in (image, image_2, image_3, image_4))
        if not prompt.strip() and not has_images:
            raise ValueError("Prompt or image required")

        size = resolve_size(quality, aspect_ratio, QUALITY_IMAGE,
                            img_shape=image.shape if image is not None else None)

        if has_images:
            refs = []
            for ref in (image, image_2, image_3, image_4):
                if ref is not None:
                    refs.append(_pil_to_b64(_tensor_to_pil(ref)))
            p = prompt.strip() or "Merge these images into one cohesive composition"
            urls = generate_image(key, p, images_b64=refs, size=size)
        else:
            urls = generate_image(key, prompt.strip(), size=size)

        tensors = []
        for loc in urls:
            if loc.startswith("http"):
                import urllib.request
                resp = urllib.request.urlopen(loc, timeout=120)
                img = Image.open(BytesIO(resp.read())).convert("RGB")
            else:
                img = Image.open(loc).convert("RGB")
            tensors.append(_pil_to_tensor(img))

        return (torch.cat(tensors, dim=0) if len(tensors) > 1 else tensors[0],)


NODE_CLASS_MAPPINGS = {"AgnesImage": AgnesImage}
NODE_DISPLAY_NAME_MAPPINGS = {"AgnesImage": "Agnes-AI Image"}
