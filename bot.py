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
from openai import OpenAI

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

# Gunakan OpenAI SDK resmi -> AgentRouter memblokir klien yang tidak dikenali.
ai_client = OpenAI(
    api_key=config.AGENTROUTER_API_KEY,
    base_url=config.AGENTROUTER_BASE_URL,
)

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

    messages = [{"role": "system", "content": config.SYSTEM_PROMPT}]
    messages.extend(history[chat_id])
    messages.append({"role": "user", "content": user_text})

    completion = ai_client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=config.TEMPERATURE,
    )
    answer = (completion.choices[0].message.content or "").strip()

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
                    "Contoh model: `gpt-5`, `claude-sonnet-4-5-20250929`, `deepseek-v3`",
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
