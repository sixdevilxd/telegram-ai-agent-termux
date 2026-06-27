"""
ai.py — Otak agent: memanggil AgentRouter (Claude) dengan loop tool-use
ala Claude Code, plus dukungan analisa gambar (vision).
"""
import json
import requests

import config
import tools

AR_URL = f"{config.AGENTROUTER_BASE_URL.rstrip('/')}/messages"

# Wire image Claude Code -> wajib agar lolos WAF/whitelist AgentRouter.
HEADERS = {
    "Authorization": f"Bearer {config.AGENTROUTER_API_KEY}",
    "Content-Type": "application/json",
    "User-Agent": "claude-cli/2.1.158 (external, sdk-cli)",
    "anthropic-version": "2023-06-01",
    "anthropic-beta": "claude-code-20250219,interleaved-thinking-2025-05-14,effort-2025-11-24,redact-thinking-2026-02-12",
    "anthropic-dangerous-direct-browser-access": "true",
    "x-app": "cli",
    "X-Stainless-Lang": "js",
    "X-Stainless-Package-Version": "0.60.0",
    "X-Stainless-OS": "Linux",
    "X-Stainless-Arch": "arm64",
    "X-Stainless-Runtime": "node",
    "X-Stainless-Runtime-Version": "v20.0.0",
}

MAX_TOOL_LOOPS = 6


def _call_api(model, messages, use_tools=True):
    body = {
        "model": model,
        "max_tokens": config.MAX_TOKENS,
        "system": config.SYSTEM_PROMPT,
        "messages": messages,
        "temperature": config.TEMPERATURE,
    }
    if use_tools:
        body["tools"] = tools.TOOLS
    r = requests.post(AR_URL, headers=HEADERS, json=body, timeout=180)
    # AgentRouter kadang membalas JSON valid dengan content-type 'text/plain',
    # atau halaman HTML dari WAF. Jadi: coba parse JSON apa adanya.
    try:
        data = r.json()
    except ValueError:
        raise RuntimeError(f"AgentRouter balas non-JSON (HTTP {r.status_code}, kemungkinan WAF): {r.text[:200].strip()}")
    if r.status_code != 200 or "error" in data:
        err = data.get("error") if isinstance(data, dict) else r.text[:200]
        raise RuntimeError(f"AgentRouter HTTP {r.status_code}: {err}")
    return data


def _text_of(content_blocks):
    return "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text").strip()


def run_agent(model, history, user_text, image_b64=None, media_type=None):
    """
    Jalankan satu giliran agent.
    - history: list pesan sebelumnya (role/content) — akan diperbarui di pemanggil.
    - image_b64/media_type: jika ada gambar (analisa chart).
    Mengembalikan (jawaban_teks, daftar_tool_yang_dipakai).
    """
    # Susun konten pesan user (teks + opsional gambar)
    if image_b64:
        user_content = [
            {"type": "image", "source": {"type": "base64", "media_type": media_type or "image/jpeg", "data": image_b64}},
            {"type": "text", "text": user_text or "Analisa chart pada gambar ini secara teknikal."},
        ]
    else:
        user_content = user_text

    messages = list(history) + [{"role": "user", "content": user_content}]
    tools_used = []

    for _ in range(MAX_TOOL_LOOPS):
        try:
            data = _call_api(model, messages, use_tools=True)
        except RuntimeError as e:
            # Kalau model/route menolak parameter tools, coba lagi tanpa tools.
            if "tools" in str(e).lower() or "400" in str(e):
                data = _call_api(model, messages, use_tools=False)
            else:
                raise

        blocks = data.get("content", [])
        stop = data.get("stop_reason")

        if stop == "tool_use":
            # Simpan langkah asisten (berisi tool_use), lalu jalankan tool.
            messages.append({"role": "assistant", "content": blocks})
            results = []
            for b in blocks:
                if b.get("type") == "tool_use":
                    name, args, tid = b.get("name"), b.get("input", {}), b.get("id")
                    tools_used.append(name)
                    output = tools.execute_tool(name, args)
                    results.append({"type": "tool_result", "tool_use_id": tid, "content": output})
            messages.append({"role": "user", "content": results})
            continue

        # Selesai — kembalikan teks final.
        return _text_of(blocks) or "_(model tidak mengembalikan teks)_", tools_used

    return "⚠️ Terlalu banyak langkah tool, dihentikan. Coba pertanyaan lebih spesifik.", tools_used
