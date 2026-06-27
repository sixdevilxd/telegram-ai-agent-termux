"""
Konfigurasi bot. Semua nilai sensitif dibaca dari environment / file .env.
Jangan pernah menaruh API key langsung di file ini.
"""
import os
from dotenv import load_dotenv

# Muat variabel dari file .env (jika ada)
load_dotenv()

# ---- Kredensial wajib ----
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
AGENTROUTER_API_KEY = os.getenv("AGENTROUTER_API_KEY", "").strip()

# ---- Pengaturan AgentRouter (route Anthropic / Claude Code) ----
AGENTROUTER_BASE_URL = os.getenv("AGENTROUTER_BASE_URL", "https://agentrouter.org/v1").strip()
# Model default. AgentRouter umumnya hanya mengizinkan claude-opus-4-6 di sebagian plan.
MODEL = os.getenv("MODEL", "claude-opus-4-6").strip()

# ---- Perilaku AI ----
SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "Kamu adalah asisten AI yang ramah, cerdas, dan membantu. "
    "Jawab dengan bahasa yang sama seperti yang digunakan pengguna. "
    "Berikan jawaban yang jelas, ringkas, dan akurat.",
).strip()

# Suhu / kreativitas jawaban (0.0 - 2.0)
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))

# Maksimum pasang pesan (user+assistant) yang diingat per chat
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "12"))

# Maksimum token jawaban (wajib untuk route Anthropic)
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))

# Daftar user ID Telegram yang diizinkan (kosong = semua orang boleh).
# Contoh di .env: ALLOWED_USERS=12345678,98765432
_allowed = os.getenv("ALLOWED_USERS", "").strip()
ALLOWED_USERS = {int(x) for x in _allowed.split(",") if x.strip().isdigit()} if _allowed else set()


def validate():
    """Pastikan kredensial wajib sudah diisi."""
    missing = []
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not AGENTROUTER_API_KEY:
        missing.append("AGENTROUTER_API_KEY")
    if missing:
        raise SystemExit(
            "❌ Konfigurasi belum lengkap. Variabel berikut kosong: "
            + ", ".join(missing)
            + "\n   Salin .env.example menjadi .env lalu isi nilainya."
        )
