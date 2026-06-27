#!/usr/bin/env python3
"""
Telegram AI Agent — CIPHER
Bot Telegram research-agent crypto (ditenagai AgentRouter/Claude) untuk Termux.

Kemampuan: web research, crypto & token research (DexScreener/CoinGecko/
GeckoTerminal), new pairs / "sniper" detection, rugcheck + anti-whale,
analisa teknikal, analisa GAMBAR chart (vision), coding/encode, riset sosmed
(Reddit + web), analisa narasi/hype — semua via tool-use otomatis.

Perintah:
  /start /help /reset /model /whoami
  /trending           - coin trending
  /new <network>      - pair/pool baru (solana/eth/bsc/base)
  /rug <address>      - rugcheck token Solana
Selain itu cukup chat biasa atau kirim screenshot chart.
"""
import sys
import time
import base64
import logging
from collections import defaultdict, deque

import requests

import config
import ai

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("cipher")

config.validate()
TG_API = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
TG_FILE = f"https://api.telegram.org/file/bot{config.TELEGRAM_BOT_TOKEN}"

history = defaultdict(lambda: deque(maxlen=config.MAX_HISTORY * 2))
chat_model = {}


# ---------------- Telegram helpers ----------------
def tg(method, **params):
    try:
        return requests.post(f"{TG_API}/{method}", json=params, timeout=65).json()
    except requests.RequestException as e:
        log.warning("Telegram %s gagal: %s", method, e)
        return {"ok": False, "error": str(e)}


def _split(text, size=4000):
    text = text or "(kosong)"
    return [text[i:i + size] for i in range(0, len(text), size)]


def send_message(chat_id, text, reply_to=None):
    for chunk in _split(text):
        p = {"chat_id": chat_id, "text": chunk, "parse_mode": "Markdown",
             "disable_web_page_preview": True}
        if reply_to:
            p["reply_to_message_id"] = reply_to
            reply_to = None
        if not tg("sendMessage", **p).get("ok"):
            p.pop("parse_mode", None)
            tg("sendMessage", **p)


def send_typing(chat_id):
    tg("sendChatAction", chat_id=chat_id, action="typing")


def download_photo(file_id):
    """Unduh foto Telegram -> (base64, media_type)."""
    info = tg("getFile", file_id=file_id)
    if not info.get("ok"):
        return None, None
    path = info["result"]["file_path"]
    r = requests.get(f"{TG_FILE}/{path}", timeout=60)
    r.raise_for_status()
    mt = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    return base64.b64encode(r.content).decode(), mt


# ---------------- Logika ----------------
def is_allowed(uid):
    return not config.ALLOWED_USERS or uid in config.ALLOWED_USERS


def run_and_reply(chat_id, text, msg_id, image_b64=None, media_type=None):
    send_typing(chat_id)
    model = chat_model.get(chat_id, config.MODEL)
    try:
        answer, used = ai.run_agent(model, history[chat_id], text,
                                    image_b64=image_b64, media_type=media_type)
        # Simpan ke memori (versi teks saja, gambar tidak disimpan)
        history[chat_id].append({"role": "user", "content": text or "[gambar chart]"})
        history[chat_id].append({"role": "assistant", "content": answer})
        if used:
            answer += f"\n\n`🔧 tools: {', '.join(dict.fromkeys(used))}`"
        send_message(chat_id, answer, reply_to=msg_id)
    except Exception as e:  # noqa: BLE001
        log.exception("agent error")
        send_message(chat_id, f"⚠️ Error saat memproses.\n`{type(e).__name__}: {e}`")


def handle_message(msg):
    chat_id = msg["chat"]["id"]
    uid = msg.get("from", {}).get("id")
    msg_id = msg.get("message_id")
    text = (msg.get("text") or msg.get("caption") or "").strip()

    if not is_allowed(uid):
        send_message(chat_id, "⛔ Kamu tidak diizinkan memakai bot ini.")
        return

    # ----- Gambar (analisa chart) -----
    if msg.get("photo"):
        send_typing(chat_id)
        try:
            file_id = msg["photo"][-1]["file_id"]  # resolusi tertinggi
            b64, mt = download_photo(file_id)
            if not b64:
                send_message(chat_id, "⚠️ Gagal mengunduh gambar.")
                return
            run_and_reply(chat_id, text, msg_id, image_b64=b64, media_type=mt)
        except Exception as e:  # noqa: BLE001
            send_message(chat_id, f"⚠️ Gagal proses gambar: `{e}`")
        return

    if not text:
        send_message(chat_id, "Kirim teks atau screenshot chart 🙂")
        return

    # ----- Perintah -----
    if text.startswith("/"):
        cmd, _, arg = text.partition(" ")
        cmd = cmd.split("@")[0].lower()
        arg = arg.strip()
        if cmd == "/start":
            send_message(chat_id,
                "```\n  ____ ___ ____  _   _ _____ ____\n |  _ \\_ _|  _ \\| | | | ____|  _ \\\n | |_) | || |_) | |_| |  _| | |_) |\n |  __/| ||  __/|  _  | |___|  _ <\n |_|  |___|_|   |_| |_|_____|_| \\_\\\n```\n"
                "*CIPHER* — AI research agent crypto 🧬\n\n"
                "Tanya apa saja, contoh:\n"
                "• `analisa $SOL secara teknikal`\n"
                "• `cek rugcheck <contract address>`\n"
                "• `token apa yang lagi hype hari ini?`\n"
                "• `pair baru di solana`\n"
                "• kirim *screenshot chart* untuk dianalisa\n\n"
                "Ketik /help untuk daftar lengkap.")
        elif cmd == "/help":
            send_message(chat_id,
                "*Perintah:*\n"
                "/trending — coin trending\n"
                "/new `<network>` — pair baru (solana/eth/bsc/base)\n"
                "/rug `<address>` — rugcheck token Solana\n"
                "/model `<nama>` — ganti model\n"
                "/reset — hapus memori\n"
                "/whoami — id kamu\n\n"
                "Selebihnya cukup *chat biasa* atau *kirim gambar chart*. "
                "CIPHER otomatis memakai web search, data DEX, rugcheck, TA, Reddit, dll.\n\n"
                "_DYOR — bukan saran finansial._")
        elif cmd == "/reset":
            history.pop(chat_id, None)
            send_message(chat_id, "🧹 Memori dihapus.")
        elif cmd == "/model":
            if arg:
                chat_model[chat_id] = arg
                send_message(chat_id, f"✅ Model: `{arg}`")
            else:
                send_message(chat_id, f"Model aktif: `{chat_model.get(chat_id, config.MODEL)}`\n"
                                      "Ganti: `/model claude-opus-4-6`")
        elif cmd == "/whoami":
            send_message(chat_id, f"user_id: `{uid}`\nchat_id: `{chat_id}`")
        elif cmd == "/trending":
            run_and_reply(chat_id, "Tampilkan coin yang sedang trending dan narasinya.", msg_id)
        elif cmd == "/new":
            net = arg or "solana"
            run_and_reply(chat_id, f"Tampilkan pair/pool baru di {net} dan ingatkan untuk rugcheck.", msg_id)
        elif cmd == "/rug":
            if not arg:
                send_message(chat_id, "Pakai: `/rug <contract_address>`")
            else:
                run_and_reply(chat_id, f"Rugcheck token ini dan analisa anti-whale: {arg}", msg_id)
        else:
            send_message(chat_id, "Perintah tidak dikenal. /help")
        return

    # ----- Chat biasa -> agent -----
    run_and_reply(chat_id, text, msg_id)


def main():
    me = tg("getMe")
    if not me.get("ok"):
        raise SystemExit(f"❌ Token Telegram tidak valid / tidak ada internet. {me}")
    log.info("CIPHER aktif sebagai @%s | model '%s'", me["result"].get("username"), config.MODEL)
    log.info("Ctrl+C untuk berhenti.")
    offset = None
    while True:
        try:
            res = tg("getUpdates", offset=offset, timeout=60, allowed_updates=["message"])
            if not res.get("ok"):
                time.sleep(3)
                continue
            for u in res["result"]:
                offset = u["update_id"] + 1
                if "message" in u:
                    handle_message(u["message"])
        except KeyboardInterrupt:
            log.info("Berhenti. 👋")
            sys.exit(0)
        except Exception:  # noqa: BLE001
            log.exception("loop error, lanjut 3 detik...")
            time.sleep(3)


if __name__ == "__main__":
    main()
