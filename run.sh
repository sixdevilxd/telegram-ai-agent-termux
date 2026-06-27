#!/data/data/com.termux/files/usr/bin/bash
# Skrip jalan-cepat untuk Termux.
# Pemakaian: bash run.sh
set -e

cd "$(dirname "$0")"

# Pastikan dependensi terpasang
if ! python -c "import openai" 2>/dev/null; then
  echo "📦 Memasang dependensi..."
  pip install -r requirements.txt
fi

# Pastikan .env ada
if [ ! -f .env ]; then
  echo "❌ File .env belum ada."
  echo "   Jalankan: cp .env.example .env  lalu isi token-nya (nano .env)."
  exit 1
fi

echo "🚀 Menjalankan bot..."
python bot.py
