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

const TEXT_MODELS = [
    "agnes-3.0-flash",
    "agnes-2.5-pro",
    "agnes-2.5-pro-beta",
    "agnes-2.5-flash",
];
const IMAGE_MODELS = [
    "agnes-image-2.5-flash",
    "agnes-image-2.1-flash",
    "agnes-image-2.0-flash",
];
const VIDEO_MODELS = [
    "agnes-video-2.5-flash",
    "agnes-video-2.5",
    "agnes-video-v2.0",
];

// ── Settings ────────────────────────────────────────────────────────
// NOTE: ComfyUI sorts sections alphabetically by category[1],
//       and items within a section appear in REVERSE insertion order.
//       So items are inserted in REVERSE of the desired display order.

const agnesSettings = [

    // ══════════════════════════════════════════════════════════════════
    // Section 1: API Key  (category[1] = "API Key" → sorts first: A)
    // ══════════════════════════════════════════════════════════════════
    // Custom item — renders key list with delete buttons + add key input + failover subtitle + link
    {
        id: "Agnes-AI.apiKeys",
        name: "API Key",
        category: ["⚡Agnes-AI", "API Key", "API Key"],
        type: () => {
            const container = document.createElement("div");
            container.style.cssText = "display:flex; flex-direction:column; gap:8px; max-width:380px; width:100%;";

            // Existing keys list container
            const listContainer = document.createElement("div");
            listContainer.style.cssText = "display:flex; flex-direction:column; gap:6px;";

            // Add new key input row
            const addRow = document.createElement("div");
            addRow.style.cssText = "display:flex; gap:8px; align-items:center;";

            const input = document.createElement("input");
            input.type = "password";
            input.autocomplete = "new-password";
            input.setAttribute("data-lpignore", "true");
            input.placeholder = "Paste new API key (sk-...)";
            input.style.cssText = [
                "flex: 1",
                "padding: 6px 10px",
                "background: var(--comfy-input-bg, #222)",
                "border: 1px solid var(--border-color, #444)",
                "border-radius: 6px",
                "color: var(--input-text, #ddd)",
                "font-size: 13px",
                "outline: none",
            ].join(";");

            const addBtn = document.createElement("button");
            addBtn.textContent = "+ Add";
            addBtn.style.cssText = [
                "padding: 6px 14px",
                "background: var(--comfy-primary, #6c5ce7)",
                "color: #fff",
                "border: none",
                "border-radius: 6px",
                "cursor: pointer",
                "font-size: 13px",
                "font-weight: 500",
                "white-space: nowrap",
            ].join(";");

            addRow.appendChild(input);
            addRow.appendChild(addBtn);

            // Bottom row: subtitle + Get API link
            const bottomRow = document.createElement("div");
            bottomRow.style.cssText = "display:flex; justify-content:space-between; align-items:center; margin-top:2px;";

            const subtitle = document.createElement("span");
            subtitle.textContent = "Supports multiple backup keys for automatic failover.";
            subtitle.style.cssText = "font-size:11px; color:var(--p-text-muted-color, #888);";

            const link = document.createElement("a");
            link.textContent = "Get API 🔑";
            link.href = "https://platform.agnes-ai.com";
            link.target = "_blank";
            link.style.cssText = "font-size:12px; color:var(--comfy-primary, #6c5ce7); text-decoration:none; font-weight:500; white-space:nowrap; margin-left:12px;";

            bottomRow.appendChild(subtitle);
            bottomRow.appendChild(link);

            container.appendChild(listContainer);
            container.appendChild(addRow);
            container.appendChild(bottomRow);

            const renderKeys = (keys) => {
                listContainer.innerHTML = "";
                if (!keys || keys.length === 0) {
                    const emptyTip = document.createElement("div");
                    emptyTip.textContent = "No API key configured yet.";
                    emptyTip.style.cssText = "font-size:12px; color:var(--p-text-muted-color, #777); padding:4px 0;";
                    listContainer.appendChild(emptyTip);
                    return;
                }

                keys.forEach((maskedKey, idx) => {
                    const item = document.createElement("div");
                    item.style.cssText = [
                        "display: flex",
                        "align-items: center",
                        "justify-content: space-between",
                        "padding: 5px 10px",
                        "background: var(--comfy-menu-bg, #1e1e24)",
                        "border: 1px solid var(--border-color, #3a3a42)",
                        "border-radius: 6px",
                        "font-family: monospace",
                        "font-size: 12px",
                        "color: var(--input-text, #ccc)",
                    ].join(";");

                    const leftSpan = document.createElement("span");
                    leftSpan.style.cssText = "display:flex; align-items:center; gap:8px;";

                    const badge = document.createElement("span");
                    badge.textContent = `#${idx + 1}`;
                    badge.style.cssText = "color:var(--comfy-primary, #6c5ce7); font-weight:bold; font-size:11px;";

                    const keyText = document.createElement("span");
                    keyText.textContent = maskedKey;

                    leftSpan.appendChild(badge);
                    leftSpan.appendChild(keyText);

                    const delBtn = document.createElement("button");
                    delBtn.innerHTML = "&times;";
                    delBtn.title = "Delete this key";
                    delBtn.style.cssText = [
                        "background: transparent",
                        "border: none",
                        "color: var(--p-text-muted-color, #888)",
                        "font-size: 16px",
                        "cursor: pointer",
                        "padding: 0 4px",
                        "line-height: 1",
                        "border-radius: 4px",
                    ].join(";");
                    delBtn.addEventListener("mouseenter", () => {
                        delBtn.style.color = "#ff4d4f";
                        delBtn.style.background = "rgba(255, 77, 79, 0.15)";
                    });
                    delBtn.addEventListener("mouseleave", () => {
                        delBtn.style.color = "var(--p-text-muted-color, #888)";
                        delBtn.style.background = "transparent";
                    });
                    delBtn.addEventListener("click", async (e) => {
                        e.preventDefault();
                        await saveConfig({ delete_index: idx });
                        loadAndRender();
                        showToast(`API Key #${idx + 1} removed`);
                    });

                    item.appendChild(leftSpan);
                    item.appendChild(delBtn);
                    listContainer.appendChild(item);
                });
            };

            const loadAndRender = () => {
                fetch("/agnes/get_config")
                    .then((r) => r.json())
                    .then((config) => {
                        renderKeys(config.api_keys || []);
                    })
                    .catch(() => {});
            };

            const doAdd = async () => {
                const val = input.value.trim();
                if (!val) return;
                await saveConfig({ add_key: val });
                input.value = "";
                loadAndRender();
                showToast("API Key added");
            };

            addBtn.addEventListener("click", (e) => {
                e.preventDefault();
                doAdd();
            });
            input.addEventListener("keydown", (e) => {
                if (e.key === "Enter") {
                    e.preventDefault();
                    doAdd();
                }
            });

            loadAndRender();
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
        defaultValue: VIDEO_MODELS[0],
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
        defaultValue: IMAGE_MODELS[0],
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
        defaultValue: TEXT_MODELS[0],
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
});

