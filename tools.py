"""
tools.py — Kumpulan "alat" realtime untuk si AI agent.

Setiap fungsi memanggil API gratis (tanpa API key) lalu mengembalikan
ringkasan berbentuk STRING yang siap dibaca model. Semua dibungkus try/except
supaya error tidak membuat bot mati — error dikembalikan sebagai teks agar
model bisa menjelaskannya ke pengguna.
"""
from __future__ import annotations

import time
import html
import json
import urllib.parse
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

# Session global dengan header "manusiawi"
S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36",
    "Accept": "application/json, text/html;q=0.9,*/*;q=0.8",
})
TIMEOUT = 25


def _get(url, **kw):
    kw.setdefault("timeout", TIMEOUT)
    return S.get(url, **kw)


def _age(ms: int | float) -> str:
    """Ubah timestamp (ms) jadi umur yang mudah dibaca."""
    try:
        secs = max(0, time.time() - (ms / 1000.0))
        if secs < 3600:
            return f"{int(secs/60)}m"
        if secs < 86400:
            return f"{secs/3600:.1f}h"
        return f"{secs/86400:.1f}d"
    except Exception:
        return "?"


def _num(x) -> str:
    """Format angka jadi ringkas (1.2K, 3.4M, 5.6B)."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "?"
    for unit, div in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(x) >= div:
            return f"{x/div:.2f}{unit}"
    return f"{x:.4g}"


# ---------------------------------------------------------------------------
# 1) Web search (DuckDuckGo)
# ---------------------------------------------------------------------------
def web_search(query: str, max_results: int = 6) -> str:
    try:
        r = S.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            timeout=TIMEOUT,
        )
        soup = BeautifulSoup(r.text, "html.parser")
        out = []
        for res in soup.select(".result")[: max_results * 2]:
            a = res.select_one(".result__a")
            snip = res.select_one(".result__snippet")
            if not a:
                continue
            href = a.get("href", "")
            # DuckDuckGo membungkus link asli di param uddg
            if "uddg=" in href:
                href = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
            out.append(f"• {a.get_text(strip=True)}\n  {href}\n  {snip.get_text(strip=True) if snip else ''}")
            if len(out) >= max_results:
                break
        return "Hasil web search:\n" + "\n".join(out) if out else "Tidak ada hasil."
    except Exception as e:
        return f"web_search error: {e}"


def fetch_url(url: str, max_chars: int = 3500) -> str:
    try:
        r = _get(url)
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = " ".join(soup.get_text(" ").split())
        return f"Isi {url}:\n{text[:max_chars]}"
    except Exception as e:
        return f"fetch_url error: {e}"


# ---------------------------------------------------------------------------
# 2) CoinGecko — harga, market, trending
# ---------------------------------------------------------------------------
CG = "https://api.coingecko.com/api/v3"


def _cg_find(query: str):
    """Cari coin id di CoinGecko dari nama/simbol."""
    r = _get(f"{CG}/search", params={"query": query})
    coins = r.json().get("coins", [])
    return coins[0] if coins else None


def crypto_overview(query: str) -> str:
    try:
        c = _cg_find(query)
        if not c:
            return f"Coin '{query}' tidak ditemukan di CoinGecko."
        cid = c["id"]
        r = _get(f"{CG}/coins/markets", params={
            "vs_currency": "usd", "ids": cid,
            "price_change_percentage": "1h,24h,7d",
        })
        d = r.json()
        if not d:
            return f"Data market untuk {cid} kosong."
        m = d[0]
        return (
            f"📊 {m['name']} ({m['symbol'].upper()})\n"
            f"Harga: ${m['current_price']:,}\n"
            f"Market cap: ${_num(m.get('market_cap'))} (rank #{m.get('market_cap_rank','?')})\n"
            f"Vol 24h: ${_num(m.get('total_volume'))}\n"
            f"Perubahan: 1h {m.get('price_change_percentage_1h_in_currency') or 0:+.2f}% | "
            f"24h {m.get('price_change_percentage_24h_in_currency') or 0:+.2f}% | "
            f"7d {m.get('price_change_percentage_7d_in_currency') or 0:+.2f}%\n"
            f"ATH: ${m.get('ath')} ({m.get('ath_change_percentage',0):+.1f}% dari ATH)"
        )
    except Exception as e:
        return f"crypto_overview error: {e}"


def trending_coins() -> str:
    try:
        r = _get(f"{CG}/search/trending")
        coins = r.json().get("coins", [])[:10]
        lines = []
        for i, c in enumerate(coins, 1):
            it = c["item"]
            chg = (it.get("data", {}) or {}).get("price_change_percentage_24h", {}).get("usd")
            chg = f"{chg:+.1f}%" if isinstance(chg, (int, float)) else "?"
            lines.append(f"{i}. {it['name']} ({it['symbol'].upper()}) — rank #{it.get('market_cap_rank','?')} | 24h {chg}")
        return "🔥 Trending di CoinGecko:\n" + "\n".join(lines)
    except Exception as e:
        return f"trending_coins error: {e}"


# ---------------------------------------------------------------------------
# 3) DexScreener — cari token/pair lintas DEX
# ---------------------------------------------------------------------------
def dex_search(query: str, limit: int = 6) -> str:
    try:
        r = _get("https://api.dexscreener.com/latest/dex/search", params={"q": query})
        pairs = r.json().get("pairs", []) or []
        pairs = sorted(pairs, key=lambda p: (p.get("liquidity", {}) or {}).get("usd", 0), reverse=True)[:limit]
        if not pairs:
            return f"Tidak ada pair untuk '{query}' di DexScreener."
        out = []
        for p in pairs:
            ch = p.get("priceChange", {}) or {}
            out.append(
                f"• {p.get('baseToken',{}).get('symbol','?')}/{p.get('quoteToken',{}).get('symbol','?')} "
                f"@ {p.get('dexId','?')} ({p.get('chainId','?')})\n"
                f"  Harga ${p.get('priceUsd','?')} | Liq ${_num((p.get('liquidity',{}) or {}).get('usd'))} | "
                f"Vol24h ${_num((p.get('volume',{}) or {}).get('h24'))}\n"
                f"  Δ 5m {ch.get('m5',0)}% | 1h {ch.get('h1',0)}% | 24h {ch.get('h24',0)}% | "
                f"umur {_age(p.get('pairCreatedAt',0))}\n"
                f"  CA: {p.get('baseToken',{}).get('address','?')}"
            )
        return "🔎 DexScreener:\n" + "\n".join(out)
    except Exception as e:
        return f"dex_search error: {e}"


# ---------------------------------------------------------------------------
# 4) GeckoTerminal — pair/pool baru (token sniper / deteksi dini)
# ---------------------------------------------------------------------------
def new_pairs(network: str = "solana", limit: int = 8) -> str:
    try:
        net = {"sol": "solana", "eth": "eth", "ethereum": "eth",
               "bsc": "bsc", "base": "base"}.get(network.lower(), network.lower())
        r = _get(
            f"https://api.geckoterminal.com/api/v2/networks/{net}/new_pools",
            headers={"Accept": "application/json;version=20230302"},
        )
        data = r.json().get("data", [])[:limit]
        if not data:
            return f"Tidak ada pool baru untuk network '{net}'."
        out = []
        for d in data:
            a = d.get("attributes", {})
            out.append(
                f"• {a.get('name','?')}\n"
                f"  Harga ${a.get('base_token_price_usd','?')} | "
                f"Liq ${_num(a.get('reserve_in_usd'))} | "
                f"Vol24h ${_num((a.get('volume_usd',{}) or {}).get('h24'))}\n"
                f"  dibuat: {a.get('pool_created_at','?')} | Δ24h {(a.get('price_change_percentage',{}) or {}).get('h24','?')}%"
            )
        return f"🆕 Pool baru di {net} (GeckoTerminal):\n" + "\n".join(out)
    except Exception as e:
        return f"new_pairs error: {e}"


# ---------------------------------------------------------------------------
# 5) Rugcheck (Solana) — keamanan token + anti-whale (top holder)
# ---------------------------------------------------------------------------
def rugcheck(token_address: str) -> str:
    try:
        r = _get(f"https://api.rugcheck.xyz/v1/tokens/{token_address}/report")
        if r.status_code != 200:
            return f"Rugcheck tidak menemukan token ini (HTTP {r.status_code}). Pastikan ini mint address Solana."
        d = r.json()
        score = d.get("score_normalised", d.get("score", "?"))
        risks = d.get("risks", []) or []
        risk_txt = "\n".join(f"  ⚠️ {x.get('name')}: {x.get('description','')} [{x.get('level','')}]" for x in risks[:6]) or "  (tidak ada flag besar)"
        # Anti-whale: konsentrasi top holder
        holders = d.get("topHolders", []) or []
        top = holders[:5]
        whale = "\n".join(
            f"  🐋 {h.get('pct',0):.2f}% — {(h.get('address','') or '')[:6]}…"
            for h in top
        ) or "  (data holder tidak tersedia)"
        top10 = sum(h.get("pct", 0) for h in holders[:10])
        mint_auth = d.get("token", {}).get("mintAuthority")
        freeze_auth = d.get("token", {}).get("freezeAuthority")
        return (
            f"🛡️ Rugcheck {token_address[:8]}…\n"
            f"Risk score: {score} (makin rendah makin aman)\n"
            f"Mint authority: {'AKTIF ⚠️' if mint_auth else 'dicabut ✅'} | "
            f"Freeze authority: {'AKTIF ⚠️' if freeze_auth else 'dicabut ✅'}\n"
            f"Top-10 holder pegang: {top10:.1f}%\n"
            f"Flag risiko:\n{risk_txt}\n"
            f"Top holder (anti-whale):\n{whale}"
        )
    except Exception as e:
        return f"rugcheck error: {e}"


# ---------------------------------------------------------------------------
# 6) Analisa teknikal (hitung indikator sendiri)
# ---------------------------------------------------------------------------
def _ema(values, period):
    k = 2 / (period + 1)
    ema = values[0]
    out = [ema]
    for v in values[1:]:
        ema = v * k + ema * (1 - k)
        out.append(ema)
    return out


def _rsi(closes, period=14):
    if len(closes) <= period:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        gains.append(max(ch, 0))
        losses.append(max(-ch, 0))
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return 100 - (100 / (1 + rs))


def technical_analysis(query: str, days: int = 14) -> str:
    try:
        c = _cg_find(query)
        if not c:
            return f"Coin '{query}' tidak ditemukan untuk analisa teknikal."
        cid = c["id"]
        r = _get(f"{CG}/coins/{cid}/ohlc", params={"vs_currency": "usd", "days": days})
        ohlc = r.json()
        if not ohlc or len(ohlc) < 20:
            return f"Data OHLC {cid} terlalu sedikit untuk analisa."
        closes = [x[4] for x in ohlc]
        highs = [x[2] for x in ohlc]
        lows = [x[3] for x in ohlc]
        last = closes[-1]
        rsi = _rsi(closes)
        ema12 = _ema(closes, 12)[-1]
        ema26 = _ema(closes, 26)[-1]
        macd = ema12 - ema26
        sma20 = sum(closes[-20:]) / 20
        std = (sum((x - sma20) ** 2 for x in closes[-20:]) / 20) ** 0.5
        bb_up, bb_lo = sma20 + 2 * std, sma20 - 2 * std
        support = min(lows[-20:])
        resistance = max(highs[-20:])
        trend = "BULLISH 📈" if ema12 > ema26 else "BEARISH 📉"
        rsi_txt = (f"{rsi:.1f} " + ("(overbought ⚠️)" if rsi > 70 else "(oversold 🟢)" if rsi < 30 else "(netral)")) if rsi else "?"
        return (
            f"📉 Analisa Teknikal {cid.upper()} ({days}d)\n"
            f"Harga: ${last:,.6g}\n"
            f"Trend (EMA12 vs EMA26): {trend}\n"
            f"RSI(14): {rsi_txt}\n"
            f"MACD: {macd:+.6g}\n"
            f"Bollinger: atas ${bb_up:,.6g} | tengah ${sma20:,.6g} | bawah ${bb_lo:,.6g}\n"
            f"Support: ${support:,.6g} | Resistance: ${resistance:,.6g}"
        )
    except Exception as e:
        return f"technical_analysis error: {e}"


# ---------------------------------------------------------------------------
# 7) Reddit search (sentimen/narasi sosmed gratis)
# ---------------------------------------------------------------------------
def reddit_search(query: str, limit: int = 8) -> str:
    try:
        r = _get("https://www.reddit.com/search.json",
                 params={"q": query, "sort": "new", "limit": limit, "t": "week"})
        posts = r.json().get("data", {}).get("children", [])
        if not posts:
            return f"Tidak ada post Reddit untuk '{query}'."
        out = []
        for p in posts[:limit]:
            d = p["data"]
            out.append(f"• r/{d.get('subreddit')} ⬆{d.get('ups',0)} 💬{d.get('num_comments',0)}\n  {d.get('title','')}")
        return f"👽 Reddit '{query}':\n" + "\n".join(out)
    except Exception as e:
        return f"reddit_search error: {e}"


# ===========================================================================
# Definisi tool untuk Anthropic + dispatcher
# ===========================================================================
TOOLS = [
    {"name": "web_search", "description": "Cari informasi terkini di internet (berita, narasi, sentimen X/Twitter via web, dll). Pakai untuk apa pun yang butuh data realtime/umum.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "fetch_url", "description": "Ambil & baca isi teks dari sebuah URL untuk riset mendalam.",
     "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
    {"name": "crypto_overview", "description": "Harga, market cap, volume, dan perubahan harga sebuah coin/token (via CoinGecko).",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string", "description": "nama atau simbol coin, mis. bitcoin / sol"}}, "required": ["query"]}},
    {"name": "trending_coins", "description": "Daftar coin yang sedang trending/hype di CoinGecko.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "dex_search", "description": "Cari token/pair lintas DEX (harga, likuiditas, volume, umur pair, contract address). Untuk token baru/meme di Solana/ETH/BSC/Base.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string", "description": "simbol, nama, atau contract address"}}, "required": ["query"]}},
    {"name": "new_pairs", "description": "Daftar pool/pair PALING BARU di sebuah network (token sniper / deteksi dini). network: solana, eth, bsc, base.",
     "input_schema": {"type": "object", "properties": {"network": {"type": "string"}}, "required": ["network"]}},
    {"name": "rugcheck", "description": "Cek keamanan token Solana: risk score, mint/freeze authority, dan konsentrasi top holder (anti-whale). Butuh mint/contract address Solana.",
     "input_schema": {"type": "object", "properties": {"token_address": {"type": "string"}}, "required": ["token_address"]}},
    {"name": "technical_analysis", "description": "Analisa teknikal sebuah coin: RSI, MACD, EMA, Bollinger Bands, support/resistance.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "days": {"type": "integer"}}, "required": ["query"]}},
    {"name": "reddit_search", "description": "Cari diskusi/sentimen/narasi terbaru di Reddit.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
]

_DISPATCH = {
    "web_search": lambda a: web_search(a.get("query", "")),
    "fetch_url": lambda a: fetch_url(a.get("url", "")),
    "crypto_overview": lambda a: crypto_overview(a.get("query", "")),
    "trending_coins": lambda a: trending_coins(),
    "dex_search": lambda a: dex_search(a.get("query", "")),
    "new_pairs": lambda a: new_pairs(a.get("network", "solana")),
    "rugcheck": lambda a: rugcheck(a.get("token_address", "")),
    "technical_analysis": lambda a: technical_analysis(a.get("query", ""), int(a.get("days", 14) or 14)),
    "reddit_search": lambda a: reddit_search(a.get("query", "")),
}


def execute_tool(name: str, args: dict) -> str:
    fn = _DISPATCH.get(name)
    if not fn:
        return f"Tool '{name}' tidak dikenal."
    try:
        return str(fn(args or {}))[:6000]
    except Exception as e:
        return f"{name} gagal: {e}"
