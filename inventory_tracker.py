#!/usr/bin/env python3
"""
Saito Legends Inventory Tracker
================================
Monitors all products matching specific keywords and sends a Discord alert
whenever the availability of any variant changes in either direction
(restock OR going out of stock).

On first start sends a full status overview to Discord.

Configuration via environment variables:
  DISCORD_WEBHOOK_URL  (required)
  POLL_INTERVAL        (optional, default 30s)
  KEYWORDS             (optional, comma-list, default: box,booster,blister,sakura)
  STATE_FILE           (optional)
"""

import json
import os
import random
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

SHOP = "https://saitolegends.com"
CATALOG_URL = SHOP + "/products.json?limit=250"

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
WA_PHONE = os.environ.get("WHATSAPP_PHONE", "").strip()
WA_APIKEY = os.environ.get("WHATSAPP_APIKEY", "").strip()
POLL_INTERVAL = float(os.environ.get("POLL_INTERVAL", "30"))
STATE_FILE = os.environ.get(
    "STATE_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "inventory_state.json"),
)

_kw_raw = os.environ.get("KEYWORDS", "box,booster,blister,sakura").strip()
KEYWORDS = [k.strip().lower() for k in _kw_raw.split(",") if k.strip()]

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

_ssl_ctx = ssl.create_default_context()


def log(msg):
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {msg}", flush=True)


def matches(title):
    t = title.lower()
    return any(kw in t for kw in KEYWORDS)


def fetch_variants():
    sep = "&" if "?" in CATALOG_URL else "?"
    url = f"{CATALOG_URL}{sep}_t={int(time.time() * 1000)}{random.randint(100, 999)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Cache-Control": "no-cache, no-store",
        },
    )
    with urllib.request.urlopen(req, timeout=15, context=_ssl_ctx) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    out = []
    for product in data.get("products", []):
        if not matches(product.get("title", "")):
            continue
        for variant in product.get("variants", []):
            name = product.get("title", "?")
            vtitle = variant.get("title", "")
            if vtitle and vtitle.lower() != "default title":
                name += f" ({vtitle})"
            out.append({
                "key": str(variant.get("id")),
                "name": name,
                "handle": product.get("handle", ""),
                "price": variant.get("price", "?"),
                "available": bool(variant.get("available")),
            })
    return out


def discord_send(payload, retries=3):
    if not DISCORD_WEBHOOK:
        return
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        DISCORD_WEBHOOK,
        data=data,
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"},
    )
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=15, context=_ssl_ctx) as resp:
                if 200 <= resp.status < 300:
                    return True
        except Exception as exc:
            log(f"!! Discord attempt {attempt}/{retries} failed: {exc}")
            time.sleep(2 * attempt)
    return False


def whatsapp_send(text, retries=3):
    if not WA_PHONE or not WA_APIKEY:
        return False
    url = (
        f"https://api.callmebot.com/whatsapp.php"
        f"?phone={WA_PHONE}&apikey={WA_APIKEY}"
        f"&text={urllib.parse.quote(text)}"
    )
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=15, context=_ssl_ctx) as resp:
                if 200 <= resp.status < 300:
                    return True
        except Exception as exc:
            log(f"!! WhatsApp attempt {attempt}/{retries} failed: {exc}")
        time.sleep(2 * attempt)
    return False


def notify_change(variant, is_available):
    if is_available:
        emoji, status, color = "🟢", "BACK IN STOCK", 0x2ECC71
    else:
        emoji, status, color = "🔴", "OUT OF STOCK", 0x95A5A6

    cart_link = f"{SHOP}/cart/{variant['key']}:1"
    product_link = f"{SHOP}/products/{variant['handle']}"

    description = f"**Price:** £{variant['price']}\n[Product page]({product_link})"
    if is_available:
        description += f"\n\n**[➡️ ADD TO CART]({cart_link})**"

    discord_send({
        "embeds": [{
            "title": f"{emoji} {status} — {variant['name']}",
            "description": description,
            "color": color,
            "footer": {"text": "Saito Legends Inventory Tracker"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]
    })
    wa_text = f"{emoji} {status}: {variant['name']} | £{variant['price']}"
    if is_available:
        wa_text += f" | {cart_link}"
    whatsapp_send(wa_text)


def send_overview(variants):
    lines = []
    for v in variants:
        sym = "🟢" if v["available"] else "🔴"
        lines.append(f"{sym} **{v['name']}** — £{v['price']}")

    discord_send({
        "content": (
            "📦 **Inventory Tracker started.**\n"
            f"Tracking {len(variants)} variant(s) matching: `{'`, `'.join(KEYWORDS)}`\n\n"
            "**Current status:**\n" + "\n".join(lines)
        ),
        "allowed_mentions": {"parse": []},
    })


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"available": {}, "seeded": False}


def save_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh)
    os.replace(tmp, STATE_FILE)


def run_once(state):
    variants = fetch_variants()
    if not variants:
        log("!! No products matched the keywords.")
        return

    # First run: set baseline and send overview, no change alerts
    if not state.get("seeded"):
        for v in variants:
            state["available"][v["key"]] = v["available"]
        state["seeded"] = True
        log(f"Baseline set for {len(variants)} variant(s). Sending overview to Discord.")
        send_overview(variants)
        return

    for v in variants:
        key = v["key"]
        was_available = state["available"].get(key)
        is_available = v["available"]

        if was_available is not None and was_available != is_available:
            direction = "BACK IN STOCK" if is_available else "OUT OF STOCK"
            log(f">>> CHANGE: {direction} — {v['name']}")
            notify_change(v, is_available)

        state["available"][key] = is_available


def main():
    if not DISCORD_WEBHOOK:
        log("WARNING: DISCORD_WEBHOOK_URL not set. Changes will only be logged.")

    log(f"Inventory tracker started. Keywords: {KEYWORDS}. Interval: {POLL_INTERVAL}s.")
    state = load_state()
    errors = 0

    while True:
        try:
            run_once(state)
            save_state(state)
            errors = 0
        except Exception as exc:
            errors += 1
            log(f"!! Error ({errors}): {exc!r}")

        delay = POLL_INTERVAL if not errors else min(POLL_INTERVAL * (2 ** min(errors, 5)), 300)
        time.sleep(delay)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("Stopped.")
        sys.exit(0)
