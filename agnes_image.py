import base64
import torch
from io import BytesIO
from PIL import Image
import numpy as np

from agnes_api import (
    get_api_key, generate_image, download_image, resolve_size,
    extract_input_items, QUALITY_IMAGE, ASPECT_RATIOS,
)

_io = None
try:
    import comfy_api.latest as _cal
    _io = _cal.io
except Exception:
    pass


def _pil_to_b64(img: Image.Image) -> str:
    """Convert PIL image to Data URI base64 string (required by Agnes API)."""
    buf = BytesIO()
    try:
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"data:image/png;base64,{b64}"
    finally:
        buf.close()


def _tensor_to_pil(tensor, index=0) -> Image.Image:
    i = tensor[index].cpu().numpy()
    return Image.fromarray((i * 255).astype(np.uint8))


def _pil_to_tensor(img: Image.Image):
    a = np.array(img.convert("RGB"), dtype=np.float32) / 255.0
    return torch.from_numpy(a).unsqueeze(0)


_BaseNode = getattr(_io, "ComfyNode", object) if _io is not None else object


class AgnesImage(_BaseNode):
    CATEGORY = "🧪AILab/⚡Agnes-AI"
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "execute"
    SEARCH_ALIASES = [
        "agnes", "txt2img", "img2img", "text to image", "image to image",
        "image fusion", "image merge", "generate image",
    ]

    @classmethod
    def define_schema(cls):
        if _io is None:
            return None
        return _io.Schema(
            node_id="AgnesImage",
            display_name="Agnes-AI Image",
            category="🧪AILab/⚡Agnes-AI",
            description="Agnes-AI Image Generator: text-to-image and image-to-image with auto-growing reference image slots (up to 4 images).",
            inputs=[
                _io.String.Input("prompt", multiline=True, default="",
                                 placeholder="Optional when images are connected",
                                 tooltip="Image prompt description"),
                _io.Combo.Input("quality", options=list(QUALITY_IMAGE.keys()), default="1K",
                                tooltip="Resolution quality tier"),
                _io.Combo.Input("aspect_ratio", options=ASPECT_RATIOS, default="auto",
                                tooltip="Aspect ratio. 'auto' matches input image ratio"),
                _io.Int.Input("seed", default=0, min=0, max=0xffffffffffffffff,
                              control_after_generate=True,
                              tooltip="Random seed (0 = random)"),
                _io.Autogrow.Input(
                    id="images",
                    template=_io.Autogrow.TemplatePrefix(
                        input=_io.Image.Input("image", optional=True, tooltip="Reference image"),
                        prefix="image_", min=0, max=4
                    ),
                    display_name="Reference Images",
                    optional=True,
                    tooltip="Input images for image-to-image / multi-image fusion (starts with image_0, up to 4 total, auto-grows as connected)"
                ),
            ],
            outputs=[
                _io.Image.Output("images", display_name="images")
            ]
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
        prompt = kwargs.get("prompt", "")
        quality = kwargs.get("quality", "1K")
        aspect_ratio = kwargs.get("aspect_ratio", "auto")
        seed = kwargs.get("seed", 0)

        key = get_api_key("AgnesImage")
        if not key:
            raise ValueError("API key required — set it in ComfyUI Settings Panel → Agnes-AI")

        # Collect images (supporting V3 autogrow 'images' dict, image, image_0..3, etc.)
        raw_images = []
        if kwargs.get("image") is not None:
            raw_images.append(kwargs["image"])
        raw_images.extend(extract_input_items(kwargs, "images", "image_"))

        raw_images = [img for img in raw_images if img is not None][:4]
        has_images = len(raw_images) > 0

        p = str(prompt).strip()
        if not p and not has_images:
            raise ValueError("Prompt or at least one image required")

        primary_shape = raw_images[0].shape if has_images else None
        size = resolve_size(quality, aspect_ratio, QUALITY_IMAGE, img_shape=primary_shape)

        try:
            actual_seed = int(seed) if seed is not None and str(seed).strip() else 0
        except (ValueError, TypeError):
            actual_seed = 0
        actual_seed = actual_seed if actual_seed > 0 else None

        if has_images:
            refs = [_pil_to_b64(_tensor_to_pil(ref)) for ref in raw_images]
            final_prompt = p or "Merge these images into one cohesive composition"
            urls = generate_image(key, final_prompt, images_b64=refs, size=size, seed=actual_seed)
        else:
            urls = generate_image(key, p, size=size, seed=actual_seed)

        tensors = []
        for loc in urls:
            img = download_image(loc) if loc.startswith("http") else Image.open(loc).convert("RGB")
            tensors.append(_pil_to_tensor(img))

        out_tensor = torch.cat(tensors, dim=0) if tensors else _pil_to_tensor(Image.new("RGB", (64, 64), (0, 0, 0)))
        return (out_tensor,)


NODE_CLASS_MAPPINGS = {"AgnesImage": AgnesImage}
NODE_DISPLAY_NAME_MAPPINGS = {"AgnesImage": "Agnes-AI Image"}