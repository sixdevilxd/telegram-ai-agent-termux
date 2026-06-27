"""
Konfigurasi bot. Semua nilai sensitif dibaca dari environment / file .env.
Jangan pernah menaruh API key langsung di file ini.
"""
import os
from dotenv import load_dotenv

# Muat variabel dari file .env (jika ada)
load_dotenv()

# ---- Kredensial ----
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
AGENTROUTER_API_KEY = os.getenv("AGENTROUTER_API_KEY", "").strip()

# ---- Pengaturan AgentRouter (route Anthropic / Claude Code) ----
AGENTROUTER_BASE_URL = os.getenv("AGENTROUTER_BASE_URL", "https://agentrouter.org/v1").strip()
# Model default. AgentRouter umumnya hanya mengizinkan claude-opus-4-6 di sebagian plan.
MODEL = os.getenv("MODEL", "claude-opus-4-6").strip()

# ---- Provider (OpenAI-compatible, mis. NVIDIA NIM, OpenRouter, dll) ----
# Diubah default-nya ke NVIDIA NIM (DeepSeek V4 Pro) via mode 'openai'
PROVIDER = os.getenv("PROVIDER", "openai").strip().lower()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://integrate.api.nvidia.com/v1").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "deepseek-ai/deepseek-v4-pro").strip()
# Model khusus analisa GAMBAR (vision). DeepSeek V4 = teks-saja, jadi pakai VLM NVIDIA.
VISION_MODEL = os.getenv("VISION_MODEL", "meta/llama-3.2-90b-vision-instruct").strip()

# ---- Perilaku AI ----
SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    (
        "Kamu adalah CIPHER — AI research agent crypto bergaya 'coding vibes' ala terminal hacker. "
        "Kamu punya akses TOOL realtime: web_search, fetch_url, crypto_overview, trending_coins, "
        "dex_search, new_pairs, rugcheck, technical_analysis, reddit_search.\n\n"
        "ATURAN:\n"
        "1. SELALU pakai tool untuk data faktual/terkini (harga, token baru, keamanan, sentimen). "
        "JANGAN mengarang angka — kalau tidak yakin, panggil tool.\n"
        "2. Untuk pertanyaan token: gabungkan dex_search + rugcheck (keamanan & anti-whale) + technical_analysis "
        "bila relevan, lalu simpulkan.\n"
        "3. Untuk 'hype/narasi baru': pakai trending_coins + reddit_search + web_search lalu rangkum narasinya.\n"
        "4. Untuk 'token sniper/pair baru': pakai new_pairs, dan SELALU ingatkan cek rugcheck dulu.\n"
        "5. Untuk gambar chart: lakukan analisa teknikal (trend, S/R, pola candle, RSI/volume bila terlihat).\n"
        "6. Kamu jago coding: bisa menulis, men-debug, memperbaiki, dan encode/decode kode.\n\n"
        "GAYA OUTPUT (coding vibes, rapi):\n"
        "- Pakai heading tebal, blok kode ```triple backtick``` untuk kode/CA/data, dan bullet.\n"
        "- Ringkas, padat, to-the-point. Sebutkan sumber data (CoinGecko/DexScreener/Rugcheck/Reddit).\n"
        "- Jawab dengan bahasa yang sama seperti pengguna.\n"
        "- Untuk crypto, selipkan disclaimer singkat: 'DYOR, bukan saran finansial.' "
        "Kamu hanya menganalisa — TIDAK mengeksekusi transaksi/trading.\n\n"
        "CARA BERPIKIR (reasoning kuat):\n"
        "- Pikirkan langkah demi langkah sebelum menjawab; pecah masalah jadi bagian kecil.\n"
        "- Verifikasi klaim dengan tool/data, jangan berasumsi. Cross-check antar sumber kalau perlu.\n"
        "- Pertimbangkan risiko, skenario alternatif, dan bukti yang bertentangan sebelum menyimpulkan.\n"
        "- Untuk analisa token/chart: gabungkan beberapa sinyal (TA + keamanan + likuiditas + narasi), "
        "lalu beri kesimpulan + tingkat keyakinan."
    ),
).strip()

# Suhu / kreativitas jawaban (0.0 - 2.0)
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))

# Maksimum pasang pesan (user+assistant) yang diingat per chat
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "12"))

# Maksimum token jawaban
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "16384"))

# ---- Reasoning mendalam (extended thinking) ----
# true = model "berpikir" dulu sebelum menjawab -> analisa jauh lebih kuat & teliti.
REASONING = os.getenv("REASONING", "false").strip().lower() in ("1", "true", "yes", "on")
# Jatah token untuk proses berpikir (min 1024). Makin besar = makin dalam, tapi lebih lambat.
REASONING_BUDGET = int(os.getenv("REASONING_BUDGET", "8000"))

# Daftar user ID Telegram yang diizinkan (kosong = semua orang boleh).
# Contoh di .env: ALLOWED_USERS=12345678,98765432
_allowed = os.getenv("ALLOWED_USERS", "").strip()
ALLOWED_USERS = {int(x) for x in _allowed.split(",") if x.strip().isdigit()} if _allowed else set()


def validate():
    """Pastikan kredensial wajib sudah diisi."""
    missing = []
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if PROVIDER == "openai":
        if not OPENAI_API_KEY:
            missing.append("OPENAI_API_KEY (karena PROVIDER=openai)")
    else:
        if not AGENTROUTER_API_KEY:
            missing.append("AGENTROUTER_API_KEY")
    if missing:
        raise SystemExit(
            "❌ Konfigurasi belum lengkap. Variabel berikut kosong: "
            + ", ".join(missing)
            + "\n   Salin .env.example menjadi .env lalu isi nilainya."
        )