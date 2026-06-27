# 🤖 Telegram AI Agent

Bot Telegram berbasis AI yang ditenagai oleh [AgentRouter](https://agentrouter.org).
Ringan, mudah, dan dirancang untuk berjalan di **Termux** (Android) maupun komputer biasa.

## ✨ Fitur
- Ngobrol dengan AI langsung dari Telegram (mendukung gpt-5, Claude, DeepSeek, GLM, dll lewat AgentRouter).
- Ingatan percakapan per-chat (otomatis dipangkas).
- Ganti model langsung dari chat: `/model claude-sonnet-4-5-20250929`.
- Pembatasan akses opsional (hanya user tertentu).
- Tanpa framework berat — hanya `openai`, `requests`, `python-dotenv`.

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
   git clone https://github.com/USERNAME/telegram-ai-agent.git
   cd telegram-ai-agent
   ```
   > Ganti `USERNAME` dengan akun GitHub tempat repo ini berada.

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
git clone https://github.com/USERNAME/telegram-ai-agent.git
cd telegram-ai-agent
pip install -r requirements.txt
cp .env.example .env      # lalu isi token (Windows: copy .env.example .env)
python bot.py
```

---

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
| `/start`  | Mulai / sapaan |
| `/help`   | Bantuan |
| `/reset`  | Hapus ingatan percakapan |
| `/model`  | Lihat/ganti model |
| `/whoami` | Tampilkan user id & chat id |

---

## 🔒 Keamanan
- File `.env` **tidak akan** ikut ter-upload ke GitHub (sudah ada di `.gitignore`).
- Jangan pernah membagikan token atau API key kamu ke siapa pun.

## ❓ Masalah Umum
- **"Konfigurasi belum lengkap"** → file `.env` belum diisi.
- **"Token Telegram tidak valid"** → cek lagi `TELEGRAM_BOT_TOKEN`.
- **Error dari AI / "unauthorized client"** → pastikan API key AgentRouter benar dan masih punya kuota. Project ini sudah memakai OpenAI SDK resmi agar tidak diblokir.
- **Bot diam saja** → pastikan `bash run.sh` masih berjalan dan ada koneksi internet.

---
Dibuat dengan ❤️ untuk dijalankan di Termux.
