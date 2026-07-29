// web/js/agnes-settings.js
// Agnes-AI Settings Panel — ComfyUI extension pattern
import { app } from "../../../scripts/app.js";

// ── Helpers ─────────────────────────────────────────────────────────

function showToast(msg, isError = false) {
    if (app.ui && typeof app.ui.toast === "function") {
        app.ui.toast(msg);
    } else if (app.ui && app.ui.dialog && typeof app.ui.dialog.show === "function") {
        app.ui.dialog.show(msg);
    } else {
        alert(msg);
    }
    if (isError) console.error("[Agnes-AI]", msg);
    else console.log("[Agnes-AI]", msg);
}

async function saveConfig(payload) {
    try {
        const resp = await fetch("/agnes/save_config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const result = await resp.json();
        if (result.status !== "success") {
            showToast("❌ " + (result.message || "Save failed"), true);
        }
    } catch (err) {
        console.error("[Agnes-AI] Save error:", err);
        showToast("❌ Save error — check console", true);
    }
}

// ── Model options ───────────────────────────────────────────────────

const TEXT_MODELS = ["agnes-2.5-flash", "agnes-2.5-pro-alpha", "agnes-2.0-flash", "agnes-1.5-flash"];
const IMAGE_MODELS = ["agnes-image-2.1-flash", "agnes-image-2.0-flash"];
const VIDEO_MODELS = ["agnes-video-v2.0"];

// ── Settings ────────────────────────────────────────────────────────
// NOTE: ComfyUI sorts sections alphabetically by category[1],
//       and items within a section appear in REVERSE insertion order.
//       So items are inserted in REVERSE of the desired display order.

const agnesSettings = [

    // ══════════════════════════════════════════════════════════════════
    // Section 1: API Key  (category[1] = "API Key" → sorts first: A)
    // ══════════════════════════════════════════════════════════════════
    // Only one custom item — renders input + subtitle + link
    {
        id: "Agnes-AI.apiKey",
        name: "API Key",
        category: ["⚡Agnes-AI", "API Key", "API Key"],
        type: () => {
            const container = document.createElement("div");

            // Password input
            const input = document.createElement("input");
            input.type = "password";
            input.placeholder = "sk-...";
            input.style.cssText = [
                "width: 100%",
                "max-width: 340px",
                "padding: 6px 10px",
                "background: var(--comfy-input-bg, #222)",
                "border: 1px solid var(--border-color, #444)",
                "border-radius: 6px",
                "color: var(--input-text, #ddd)",
                "font-size: 14px",
                "outline: none",
            ].join(";");

            // Bottom row: small subtitle (left) + Get API link (right)
            const bottomRow = document.createElement("div");
            bottomRow.style.cssText = "display:flex; justify-content:space-between; align-items:center; margin-top:6px;";

            const subtitle = document.createElement("span");
            subtitle.textContent = "Supports multiple API keys for load balancing.";
            subtitle.style.cssText = "font-size:11px; color:var(--p-text-muted-color, #888);";

            const link = document.createElement("a");
            link.textContent = "Get API 🔑";
            link.href = "https://platform.agnes-ai.com";
            link.target = "_blank";
            link.style.cssText = "font-size:12px; color:var(--comfy-primary, #6c5ce7); text-decoration:none; font-weight:500; white-space:nowrap; margin-left:12px;";

            bottomRow.appendChild(subtitle);
            bottomRow.appendChild(link);
            container.appendChild(input);
            container.appendChild(bottomRow);

            // Load current API key (masked) into input
            fetch("/agnes/get_config")
                .then((r) => r.json())
                .then((config) => {
                    if (config.api_key_masked) {
                        input.value = config.api_key_masked;
                    }
                })
                .catch(() => { });

            // Save on change
            input.addEventListener("change", () => {
                const value = input.value.trim();
                if (!value || value.includes("****")) return;
                saveConfig({ api_key: value });
            });

            return container;
        },
    },

    // ══════════════════════════════════════════════════════════════════
    // Section 2: Models  (category[1] = "Models" → sorts second: M)
    // Desired display order: Text (top), Image, Video (bottom)
    // → Insert in REVERSE: Video, Image, Text
    // ══════════════════════════════════════════════════════════════════
    {
        id: "Agnes-AI.videoModel",
        name: "Video Model",
        type: "combo",
        defaultValue: "agnes-video-v2.0",
        options: VIDEO_MODELS,
        category: ["⚡Agnes-AI", "Models", "Video Model"],
        onChange: async (value) => {
            if (!value) return;
            await saveConfig({ video_model: value });
        },
    },
    {
        id: "Agnes-AI.imageModel",
        name: "Image Model",
        type: "combo",
        defaultValue: "agnes-image-2.1-flash",
        options: IMAGE_MODELS,
        category: ["⚡Agnes-AI", "Models", "Image Model"],
        onChange: async (value) => {
            if (!value) return;
            await saveConfig({ image_model: value });
        },
    },
    {
        id: "Agnes-AI.textModel",
        name: "Text Model",
        type: "combo",
        defaultValue: "agnes-2.5-flash",
        options: TEXT_MODELS,
        category: ["⚡Agnes-AI", "Models", "Text Model"],
        onChange: async (value) => {
            if (!value) return;
            await saveConfig({ text_model: value });
        },
    },

    // ══════════════════════════════════════════════════════════════════
    // Section 3: Resources  (category[1] = "Resources" → sorts third: R)
    // ══════════════════════════════════════════════════════════════════
    {
        id: "Agnes-AI.about",
        name: " ",
        category: ["⚡Agnes-AI", "Resources", "About"],
        type: () => {
            const container = document.createElement("div");
            container.style.cssText = "font-size:12px; line-height:1.6; color:var(--p-text-muted-color, #999); max-width:480px;";

            const p1 = document.createElement("p");
            p1.style.margin = "0 0 8px 0";
            p1.textContent =
                "ComfyUI-Agnes-AI is a custom node package for ComfyUI that integrates the free Agnes AI API, " +
                "providing a cloud-based AI generation platform. Generate images, create videos, enhance prompts, " +
                "and analyze images\u2014all without requiring a local GPU or additional Python dependencies.";

            const p2 = document.createElement("p");
            p2.style.margin = "0";
            p2.textContent = "For more information and updates, please visit our GitHub repository:";

            const linkDiv = document.createElement("div");
            linkDiv.style.marginTop = "4px";
            const link = document.createElement("a");
            link.textContent = "github.com/1038lab/ComfyUI-Agnes-AI";
            link.href = "https://github.com/1038lab/ComfyUI-Agnes-AI";
            link.target = "_blank";
            link.style.cssText = "color:var(--comfy-primary, #6c5ce7); text-decoration:none; font-weight:500;";
            linkDiv.appendChild(link);

            container.appendChild(p1);
            container.appendChild(p2);
            container.appendChild(linkDiv);
            return container;
        },
    },
];

app.registerExtension({
    name: "Agnes-AI.Settings",
    settings: agnesSettings,
    setup() {
        // Legacy bridge for older ComfyUI builds
        if (app.ui?.settings?.addSetting) {
            agnesSettings.forEach((setting) => {
                try {
                    app.ui.settings.addSetting(setting);
                } catch (err) { }
            });
        }
        console.info("[Agnes-AI] Settings registered");
    },
});
