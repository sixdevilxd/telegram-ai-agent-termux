# 🤖 Telegram AI Agent

Bot Telegram berbasis AI yang ditenagai oleh [AgentRouter](https://agentrouter.org).
Ringan, mudah, dan dirancang untuk berjalan di **Termux** (Android) maupun komputer biasa.

## ✨ Fitur
**CIPHER** — AI research agent crypto bergaya *coding vibes*, dengan tool realtime otomatis:
- 🔍 **Web research** (DuckDuckGo) + baca isi halaman
- 💰 **Crypto research** — harga/market (CoinGecko), token & pair (DexScreener)
- 🆕 **New pairs / sniper detection** (GeckoTerminal) — deteksi dini pool baru
- 🔥 **Hype & narasi** — trending coins + Reddit + web
- 🛡️ **Rugcheck** + 🐋 **anti-whale** (konsentrasi top holder) untuk token Solana
- 📊 **Analisa teknikal** — RSI, MACD, EMA, Bollinger, support/resistance
- 🖼️ **Analisa gambar chart** — kirim screenshot, dianalisa via vision
- 💻 **Coding / debug / encode** + jawab apa pun dengan data realtime
- 🧠 Semua via **tool-use agent** (Claude memilih tool yang tepat otomatis)

> ⚠️ Ini **research tool**, bukan bot trading. "Sniper" & "anti-whale" = deteksi/analisa,
> BUKAN auto-beli. Bot tidak menyentuh wallet/dana. X/Twitter & Facebook tidak diakses
> langsung (API tertutup) — sentimennya via web search + Reddit. DYOR, bukan saran finansial.

## 📋 Yang Perlu Disiapkan
1. **Token Bot Telegram** — buat lewat [@BotFather](https://t.me/BotFather): kirim `/newbot`, ikuti langkahnya, salin token-nya.
2. **API Key AgentRouter** — ambil di https://agentrouter.org/console/token

---

## 📱 Cara Pakai di Termux (Android)

1. **Install Termux** (disarankan dari F-Droid, bukan Play Store).

2. **Pasang paket dasar & clone project:**
   ```bash
   pkg update -y && pkg upgrade -y
   pkg install -y python git
   git clone https://github.com/sixdevilxd/telegram-ai-agent-termux.git
   cd telegram-ai-agent
   ```

3. **Isi kredensial:**
   ```bash
   cp .env.example .env
   nano .env
   ```
   Isi `TELEGRAM_BOT_TOKEN` dan `AGENTROUTER_API_KEY`, lalu simpan
   (di nano: `Ctrl+O` → `Enter` → `Ctrl+X`).

4. **Jalankan:**
   ```bash
   bash run.sh
   ```
   Skrip akan memasang dependensi otomatis lalu menyalakan bot.
   Buka Telegram, cari bot kamu, kirim `/start`. Selesai! 🎉

### Tips Termux
- **Agar tidak mati saat layar terkunci:** jalankan `termux-wake-lock` sebelum memulai.
- **Biar tetap jalan di latar belakang:** install `pkg install tmux`, lalu:
  ```bash
  tmux new -s bot
  bash run.sh
  ```
  Lepas sesi dengan `Ctrl+B` lalu `D`. Sambung lagi: `tmux attach -t bot`.

---

## 💻 Cara Pakai di Komputer (Linux/Mac/Windows)

```bash
git clone https://github.com/sixdevilxd/telegram-ai-agent-termux.git
cd telegram-ai-agent
pip install -r requirements.txt
cp .env.example .env      # lalu isi token (Windows: copy .env.example .env)
python bot.py
```

---

## 🔄 Provider cadangan (atasi "content-blocked")
AgentRouter punya **moderasi server** yang kadang menolak request crypto dengan error
`content-blocked` — ini dari sisi mereka, tidak bisa dimatikan dari kode. Solusinya:
pasang **provider cadangan** OpenAI-compatible; kalau AgentRouter memblokir, bot
**otomatis pindah**.

Cara (pakai OpenRouter sebagai contoh):
1. Daftar & buat API key di https://openrouter.ai/keys (ada model murah/gratis).
2. Di `.env`, isi:
   ```bash
   OPENAI_BASE_URL=https://openrouter.ai/api/v1
   OPENAI_API_KEY=sk-or-...
   OPENAI_MODEL=openai/gpt-4o-mini      # atau model lain, mis. anthropic/claude-3.5-sonnet
   ```
3. Restart bot. Selesai — fallback aktif otomatis.

> Mau langsung pakai provider cadangan sebagai UTAMA (tanpa AgentRouter)? Set `PROVIDER=openai`.
> Bekerja dengan layanan OpenAI-compatible mana pun (Groq, OpenAI, Together, dll) — cukup ganti `OPENAI_BASE_URL`/`OPENAI_MODEL`.

## ⚙️ Konfigurasi (file `.env`)

| Variabel              | Wajib | Keterangan |
|-----------------------|:-----:|------------|
| `TELEGRAM_BOT_TOKEN`  | ✅    | Token dari @BotFather |
| `AGENTROUTER_API_KEY` | ✅    | API key dari AgentRouter |
| `MODEL`               | ❌    | Model default (mis. `gpt-5`) |
| `SYSTEM_PROMPT`       | ❌    | Kepribadian/instruksi AI |
| `TEMPERATURE`         | ❌    | Kreativitas 0.0–2.0 (default 0.7) |
| `MAX_HISTORY`         | ❌    | Jumlah pasang pesan yang diingat (default 12) |
| `ALLOWED_USERS`       | ❌    | Batasi akses, mis. `12345678,98765432` |

## 💬 Perintah di Telegram
| Perintah  | Fungsi |
|-----------|--------|
| `/start`  | Sapaan |
| `/help`   | Bantuan |
| `/trending` | Coin yang sedang trending |
| `/new <network>` | Pair/pool baru (solana/eth/bsc/base) |
| `/rug <address>` | Rugcheck token Solana + anti-whale |
| `/reset`  | Hapus ingatan percakapan |
| `/model`  | Lihat/ganti model |
| `/whoami` | Tampilkan user id & chat id |

Selebihnya cukup **chat biasa** atau **kirim screenshot chart** — CIPHER otomatis
memakai web search, data DEX, rugcheck, analisa teknikal, Reddit, dll. Contoh:
- `analisa $SOL secara teknikal`
- `token apa yang lagi hype hari ini?`
- `pair baru di solana, mana yang aman?`
- `cek rugcheck <contract address>`
- `tulis script python untuk ... ` / `perbaiki kode ini: ...`

---

## 🔒 Keamanan
- File `.env` **tidak akan** ikut ter-upload ke GitHub (sudah ada di `.gitignore`).
- Jangan pernah membagikan token atau API key kamu ke siapa pun.

## ❓ Masalah Umum
- **"Konfigurasi belum lengkap"** → file `.env` belum diisi.
- **"Token Telegram tidak valid"** → cek lagi `TELEGRAM_BOT_TOKEN`.
- **`content-blocked` dari AgentRouter** → model yang kamu minta TIDAK termasuk di plan key-mu (paling sering), atau kena moderasi. Banyak plan AgentRouter hanya mengizinkan `claude-opus-4-6`. Coba `/model claude-opus-4-6` atau cek model yang diizinkan di dashboard AgentRouter.
- **Jawaban kosong / error HTML (WAF)** → request tidak menyerupai Claude Code. Bot ini sudah mengirim "wire image" Claude Code yang benar; pastikan kamu memakai versi terbaru (`git pull`).
- **Gagal install / error build `jiter` atau `pydantic-core`** → versi ini sudah TIDAK memakai paket `openai`, jadi tak ada lagi yang perlu dikompilasi. Pastikan kamu sudah `git pull` versi terbaru, lalu `pip install -r requirements.txt`.
- **Bot diam saja** → pastikan `bash run.sh` masih berjalan dan ada koneksi internet.

---
Dibuat dengan ❤️ untuk dijalankan di Termux.
