#!/usr/bin/env python3
"""
Telegram AI Agent
-----------------
Bot Telegram yang ditenagai AgentRouter (https://agentrouter.org).
Ringan, tanpa framework berat, cocok dijalankan di Termux.

Cara kerja:
- Mengambil pesan baru dari Telegram via long-polling (getUpdates).
- Mengirim percakapan ke AgentRouter (OpenAI-compatible) lalu membalas.
- Menyimpan riwayat percakapan per-chat di memori (otomatis dipangkas).

Perintah:
  /start  - mulai / sapaan
  /help   - bantuan
  /reset  - hapus ingatan percakapan di chat ini
  /model  - lihat atau ganti model, contoh: /model claude-sonnet-4-5-20250929
  /whoami - tampilkan user id & chat id kamu
"""
import sys
import time
import logging
from collections import defaultdict, deque

import requests

import config

# ----------------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("tg-ai-agent")

# ----------------------------------------------------------------------------
# Klien
# ----------------------------------------------------------------------------
config.validate()

TG_API = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"

# AgentRouter = relay Anthropic-compatible. Pakai route Messages.
AR_URL = f"{config.AGENTROUTER_BASE_URL.rstrip('/')}/messages"

# Header WAJIB menyerupai "wire image" Claude Code, kalau tidak request
# akan ditolak WAF/whitelist AgentRouter ("unauthorized client" / "content-blocked").
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

# Riwayat percakapan per chat_id (deque berisi {"role","content"})
history = defaultdict(lambda: deque(maxlen=config.MAX_HISTORY * 2))
# Model aktif per chat (default = config.MODEL)
chat_model = {}


# ----------------------------------------------------------------------------
# Helper Telegram
# ----------------------------------------------------------------------------
def tg(method: str, **params):
    """Panggil Telegram Bot API."""
    try:
        r = requests.post(f"{TG_API}/{method}", json=params, timeout=65)
        return r.json()
    except requests.RequestException as e:
        log.warning("Telegram request gagal (%s): %s", method, e)
        return {"ok": False, "error": str(e)}


def send_message(chat_id: int, text: str, reply_to: int | None = None):
    """Kirim pesan. Pesan panjang dipecah otomatis (limit Telegram 4096)."""
    for chunk in _split(text, 4000):
        params = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        if reply_to:
            params["reply_to_message_id"] = reply_to
            reply_to = None  # hanya reply pada chunk pertama
        res = tg("sendMessage", **params)
        # Jika Markdown gagal (format tidak valid), kirim ulang sebagai teks polos.
        if not res.get("ok"):
            params.pop("parse_mode", None)
            tg("sendMessage", **params)


def send_typing(chat_id: int):
    tg("sendChatAction", chat_id=chat_id, action="typing")


def _split(text: str, size: int):
    text = text or "(kosong)"
    return [text[i : i + size] for i in range(0, len(text), size)]


# ----------------------------------------------------------------------------
# Inti AI
# ----------------------------------------------------------------------------
def ask_ai(chat_id: int, user_text: str) -> str:
    """Kirim percakapan ke AgentRouter dan kembalikan jawaban."""
    model = chat_model.get(chat_id, config.MODEL)

    # Format Anthropic Messages: system terpisah, messages user/assistant bergantian.
    messages = list(history[chat_id])
    messages.append({"role": "user", "content": user_text})

    resp = requests.post(
        AR_URL,
        headers=AR_HEADERS,
        json={
            "model": model,
            "max_tokens": config.MAX_TOKENS,
            "system": config.SYSTEM_PROMPT,
            "messages": messages,
            "temperature": config.TEMPERATURE,
        },
        timeout=120,
    )
    ctype = resp.headers.get("content-type", "")
    if resp.status_code != 200 or "application/json" not in ctype:
        # WAF kadang membalas halaman HTML, bukan JSON.
        snippet = resp.text[:200].replace("\n", " ")
        raise RuntimeError(f"AgentRouter HTTP {resp.status_code} ({ctype}): {snippet}")

    data = resp.json()
    # Respon Anthropic: content = daftar blok; ambil semua blok teks.
    answer = "".join(
        b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
    ).strip()

    # Simpan ke riwayat
    history[chat_id].append({"role": "user", "content": user_text})
    history[chat_id].append({"role": "assistant", "content": answer})
    return answer or "_(model tidak mengembalikan teks)_"


# ----------------------------------------------------------------------------
# Penanganan perintah & pesan
# ----------------------------------------------------------------------------
def is_allowed(user_id: int) -> bool:
    return not config.ALLOWED_USERS or user_id in config.ALLOWED_USERS


def handle_message(msg: dict):
    chat_id = msg["chat"]["id"]
    user = msg.get("from", {})
    user_id = user.get("id")
    text = (msg.get("text") or "").strip()
    msg_id = msg.get("message_id")

    if not text:
        send_message(chat_id, "Saat ini saya hanya bisa membaca pesan teks 🙂")
        return

    if not is_allowed(user_id):
        send_message(chat_id, "⛔ Maaf, kamu tidak diizinkan memakai bot ini.")
        log.info("Tolak user tidak diizinkan: %s", user_id)
        return

    # --- Perintah ---
    if text.startswith("/"):
        cmd, _, arg = text.partition(" ")
        cmd = cmd.split("@")[0].lower()  # buang @namabot di grup
        arg = arg.strip()

        if cmd == "/start":
            send_message(
                chat_id,
                "👋 *Halo!* Saya asisten AI kamu (ditenagai AgentRouter).\n\n"
                "Langsung kirim pertanyaan apa saja.\n\n"
                "Perintah: /help",
            )
        elif cmd == "/help":
            send_message(
                chat_id,
                "*Bantuan*\n"
                "• Kirim teks biasa untuk ngobrol dengan AI.\n"
                "• /reset — hapus ingatan percakapan.\n"
                "• /model — lihat/ganti model. Contoh:\n"
                "  `/model claude-sonnet-4-5-20250929`\n"
                "• /whoami — lihat user id & chat id kamu.",
            )
        elif cmd == "/reset":
            history.pop(chat_id, None)
            send_message(chat_id, "🧹 Ingatan percakapan di chat ini sudah dihapus.")
        elif cmd == "/model":
            if arg:
                chat_model[chat_id] = arg
                send_message(chat_id, f"✅ Model diganti ke: `{arg}`")
            else:
                cur = chat_model.get(chat_id, config.MODEL)
                send_message(
                    chat_id,
                    f"Model aktif: `{cur}`\n"
                    "Ganti dengan: `/model <nama-model>`\n"
                    "Contoh model: `claude-opus-4-6`. (AgentRouter sering hanya mengizinkan model ini.)",
                )
        elif cmd == "/whoami":
            send_message(chat_id, f"user_id: `{user_id}`\nchat_id: `{chat_id}`")
        else:
            send_message(chat_id, "Perintah tidak dikenal. Ketik /help.")
        return

    # --- Pesan biasa -> AI ---
    send_typing(chat_id)
    try:
        answer = ask_ai(chat_id, text)
        send_message(chat_id, answer, reply_to=msg_id)
    except Exception as e:  # noqa: BLE001
        log.exception("Gagal memproses pesan")
        send_message(
            chat_id,
            "⚠️ Maaf, terjadi kesalahan saat menghubungi AI.\n"
            f"`{type(e).__name__}: {e}`",
        )


# ----------------------------------------------------------------------------
# Loop utama (long-polling)
# ----------------------------------------------------------------------------
def main():
    me = tg("getMe")
    if not me.get("ok"):
        raise SystemExit(
            "❌ Token Telegram tidak valid atau tidak ada koneksi internet.\n"
            f"   Respon: {me}"
        )
    bot_name = me["result"].get("username")
    log.info("Bot aktif sebagai @%s — menggunakan model '%s'", bot_name, config.MODEL)
    log.info("Tekan Ctrl+C untuk berhenti.")

    offset = None
    while True:
        try:
            res = tg("getUpdates", offset=offset, timeout=60, allowed_updates=["message"])
            if not res.get("ok"):
                time.sleep(3)
                continue
            for update in res["result"]:
                offset = update["update_id"] + 1
                if "message" in update:
                    handle_message(update["message"])
        except KeyboardInterrupt:
            log.info("Dihentikan oleh pengguna. Sampai jumpa! 👋")
            sys.exit(0)
        except Exception:  # noqa: BLE001
            log.exception("Error di loop utama, lanjut dalam 3 detik...")
            time.sleep(3)


if __name__ == "__main__":
    main()
