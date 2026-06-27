"""
ai.py — Otak agent dengan DUA backend + auto-fallback:

  • AgentRouter (route Anthropic /messages, wire image Claude Code)
  • OpenAI-compatible (mis. OpenRouter/Groq/OpenAI) lewat /chat/completions

Strategi:
  - PROVIDER=agentrouter (default): pakai AgentRouter. Kalau kena 'content-blocked'
    dan provider OpenAI dikonfigurasi, OTOMATIS pindah ke OpenAI-compatible.
  - PROVIDER=openai: langsung pakai OpenAI-compatible.

Keduanya mendukung tool-use + analisa gambar (vision).
"""
import json
import time
import requests

import config
import tools

MAX_TOOL_LOOPS = 6

# ---- AgentRouter (Anthropic) ----
AR_URL = f"{config.AGENTROUTER_BASE_URL.rstrip('/')}/messages"
AR_HEADERS = {
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

# ---- OpenAI-compatible ----
OAI_URL = f"{config.OPENAI_BASE_URL.rstrip('/')}/chat/completions"
OAI_HEADERS = {
    "Authorization": f"Bearer {config.OPENAI_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://github.com/sixdevilxd/telegram-ai-agent-termux",
    "X-Title": "CIPHER Telegram Agent",
}
OAI_TOOLS = [
    {"type": "function", "function": {"name": t["name"], "description": t["description"],
                                      "parameters": t["input_schema"]}}
    for t in tools.TOOLS
]
OAI_DEFAULT_MODEL = config.OPENAI_MODEL or "openai/gpt-4o-mini"


class ContentBlocked(RuntimeError):
    """AgentRouter menolak konten (moderasi/plan)."""


def _text_anthropic(blocks):
    return "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()


# ===========================================================================
# Backend 1: AgentRouter (Anthropic Messages)
# ===========================================================================
def _ar_call(model, messages, use_tools=True):
    body = {"model": model, "max_tokens": config.MAX_TOKENS,
            "system": config.SYSTEM_PROMPT, "messages": messages}
    if config.REASONING:
        # Extended thinking: model "berpikir" dulu. max_tokens harus > budget.
        body["thinking"] = {"type": "enabled", "budget_tokens": config.REASONING_BUDGET}
        body["max_tokens"] = config.REASONING_BUDGET + config.MAX_TOKENS
        # Saat thinking aktif, temperature tidak boleh diset (harus default).
    else:
        body["temperature"] = config.TEMPERATURE
    if use_tools:
        body["tools"] = tools.TOOLS
    last = None
    for attempt in range(3):
        r = requests.post(AR_URL, headers=AR_HEADERS, json=body, timeout=180)
        try:
            data = r.json()
        except ValueError:
            raise RuntimeError(f"AgentRouter non-JSON (HTTP {r.status_code}, WAF?): {r.text[:200].strip()}")
        err = data.get("error") if isinstance(data, dict) else None
        if err and ("content-blocked" in str(err)):
            last = err
            time.sleep(1.5 * (attempt + 1))
            continue
        if r.status_code != 200 or err:
            raise RuntimeError(f"AgentRouter HTTP {r.status_code}: {err or r.text[:200]}")
        return data
    raise ContentBlocked(str(last))


def _run_agentrouter(model, history, user_text, image_b64, media_type):
    if image_b64:
        user_content = [
            {"type": "image", "source": {"type": "base64", "media_type": media_type or "image/jpeg", "data": image_b64}},
            {"type": "text", "text": user_text or "Analisa chart pada gambar ini secara teknikal."},
        ]
    else:
        user_content = user_text
    messages = list(history) + [{"role": "user", "content": user_content}]
    used = []
    for _ in range(MAX_TOOL_LOOPS):
        try:
            data = _ar_call(model, messages, use_tools=True)
        except ContentBlocked:
            data = _ar_call(model, messages, use_tools=False)  # bisa ContentBlocked lagi -> bubble up
        blocks = data.get("content", [])
        if data.get("stop_reason") == "tool_use":
            messages.append({"role": "assistant", "content": blocks})
            results = []
            for b in blocks:
                if b.get("type") == "tool_use":
                    used.append(b.get("name"))
                    out = tools.execute_tool(b.get("name"), b.get("input", {}))
                    results.append({"type": "tool_result", "tool_use_id": b.get("id"), "content": out})
            messages.append({"role": "user", "content": results})
            continue
        return _text_anthropic(blocks) or "_(model tidak mengembalikan teks)_", used
    return "⚠️ Terlalu banyak langkah tool. Coba lebih spesifik.", used


# ===========================================================================
# Backend 2: OpenAI-compatible (chat/completions)
# ===========================================================================
def _oai_call(model, messages, use_tools=True, max_tokens=None):
    body = {"model": model, "max_tokens": max_tokens or config.MAX_TOKENS,
            "messages": messages, "temperature": config.TEMPERATURE}
    if config.REASONING:
        # OpenRouter/o-series: aktifkan reasoning. Provider yang tak mendukung akan mengabaikan.
        body["reasoning"] = {"effort": "high"}
    if use_tools:
        body["tools"] = OAI_TOOLS
        body["tool_choice"] = "auto"
    # Retry dengan backoff untuk 429 (rate limit) & 5xx (server sibuk).
    last = None
    for attempt in range(4):
        r = requests.post(OAI_URL, headers=OAI_HEADERS, json=body, timeout=180)
        if r.status_code == 429 or r.status_code >= 500:
            last = f"HTTP {r.status_code}"
            ra = r.headers.get("Retry-After")
            wait = float(ra) if (ra and ra.replace('.', '', 1).isdigit()) else (2 ** attempt) * 2
            time.sleep(min(wait, 30))
            continue
        try:
            data = r.json()
        except ValueError:
            raise RuntimeError(f"Provider OpenAI non-JSON (HTTP {r.status_code}): {r.text[:200].strip()}")
        if r.status_code != 200 or (isinstance(data, dict) and data.get("error")):
            raise RuntimeError(f"Provider OpenAI HTTP {r.status_code}: {data.get('error') if isinstance(data, dict) else r.text[:200]}")
        return data
    raise RuntimeError(
        f"Provider sibuk / kena rate limit ({last}). NVIDIA NIM free tier punya batas "
        "request per menit & kuota. Tunggu sebentar lalu coba lagi."
    )


def _run_openai(model, history, user_text, image_b64, media_type):
    # Gambar: model teks-saja (mis. DeepSeek V4) tidak bisa "melihat".
    # Routing ke model VISION NVIDIA, tanpa tool (VLM NIM tak mendukung function-calling).
    if image_b64:
        vmodel = config.VISION_MODEL or model
        vcontent = [
            {"type": "text", "text": user_text or "Analisa chart pada gambar ini secara teknikal."},
            {"type": "image_url", "image_url": {"url": f"data:{media_type or 'image/jpeg'};base64,{image_b64}"}},
        ]
        vmsgs = [{"role": "system", "content": config.SYSTEM_PROMPT}, *history,
                 {"role": "user", "content": vcontent}]
        data = _oai_call(vmodel, vmsgs, use_tools=False, max_tokens=min(config.MAX_TOKENS, 4096))
        msg = data["choices"][0]["message"]
        return (msg.get("content") or "_(model tidak mengembalikan teks)_"), []
    user_content = user_text
    messages = [{"role": "system", "content": config.SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_content})
    used = []
    for _ in range(MAX_TOOL_LOOPS):
        data = _oai_call(model, messages, use_tools=True)
        msg = data["choices"][0]["message"]
        if msg.get("tool_calls"):
            messages.append(msg)
            for tc in msg["tool_calls"]:
                name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                used.append(name)
                out = tools.execute_tool(name, args)
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": out})
            continue
        return (msg.get("content") or "_(model tidak mengembalikan teks)_"), used
    return "⚠️ Terlalu banyak langkah tool. Coba lebih spesifik.", used


# ===========================================================================
# Entry point terpadu + auto-fallback
# ===========================================================================
def run_agent(model, history, user_text, image_b64=None, media_type=None):
    """Mengembalikan (jawaban, daftar_tool). Auto-fallback AgentRouter -> OpenAI."""
    has_fallback = bool(config.OPENAI_API_KEY)

    if config.PROVIDER == "openai":
        return _run_openai(config.OPENAI_MODEL or OAI_DEFAULT_MODEL, history, user_text, image_b64, media_type)

    # Default: AgentRouter dulu
    try:
        return _run_agentrouter(model, history, user_text, image_b64, media_type)
    except ContentBlocked:
        if has_fallback:
            ans, used = _run_openai(config.OPENAI_MODEL or OAI_DEFAULT_MODEL, history, user_text, image_b64, media_type)
            return ans + f"\n\n`⚡ AgentRouter memblokir -> dialihkan ke {config.OPENAI_MODEL or OAI_DEFAULT_MODEL}`", used
        return (
            "🚫 *Request diblokir AgentRouter* (moderasi/plan) — dan provider cadangan belum diatur.\n"
            "Solusi:\n"
            "• parafrase pertanyaannya, atau\n"
            "• aktifkan fallback: isi `OPENAI_API_KEY` (mis. dari openrouter.ai) di `.env`.\n"
            "  Lihat README bagian *Provider cadangan*."
        ), []
