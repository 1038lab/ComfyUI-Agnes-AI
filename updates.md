# ComfyUI-Agnes-AI Update Log

## V1.1.0 (2026/07/29)  
**Settings Panel Integration** — Configuration moved from node to ComfyUI Settings Panel.
<img width="600" alt="agnes-ai-settings" src="https://github.com/user-attachments/assets/1ad90d3a-d2da-4c7c-bdd0-e8bfbe0d4616" />
- **New:** Integrated Agnes-AI settings directly into the ComfyUI Settings Panel (⚙️) to configure the API key and select default models for text, image, and video generation.
- **New:** Added support for `agnes-2.5-flash` and `agnes-2.5-pro-alpha` text models.
- **Improved:** Set `agnes-2.5-flash` as default text model (`agnes-2.5-pro-alpha` is available as a paid model option).
- **New:** Added negative prompt support on the Video node to easily exclude specific elements from generated videos.
- **New:** Added direct frame sequence extraction and audio track extraction outputs on the Video node (requires local `ffmpeg`).
- **New:** Integrated automated script loading to support ComfyUI's modern custom extension interface.
- **Improved:** Consolidated the API key configuration and the "Get API key" link into a single settings entry.
- **Improved:** Widened settings panel input fields so that long model names and API keys are fully visible.
- **Improved:** Made the API key global so it is set once in Settings and automatically used across all nodes.
- **Improved:** Renamed the Text node's "style" option to "preset" for better clarity and ease of use.
- **Improved:** Updated duration constraints for the Video node (extended from 2–15s to 3–18s).
- **Fixed:** Corrected image merging payload format to resolve 400 errors during image-to-image generation.
- **Fixed:** Resolved a crash that occurred when generating text-to-image variations if the server returned empty data.
- **Fixed:** Corrected image-to-image data encoding to match server format requirements.
- **Backend:** Added server communication handlers to cleanly read and write options from the Settings Panel.

## v1.0.0

Initial release with Agnes-AI Image, Video, Text, and Config nodes.
