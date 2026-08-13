#!/usr/bin/env python3
"""
Saito Legends Restock Monitor
=============================

Pollt den oeffentlichen Shopify-Produktkatalog von saitolegends.com und schickt
eine Discord-Nachricht, sobald eine ueberwachte Variante wieder auf
"available: true" springt.

Die Nachricht enthaelt einen Checkout-Direktlink (Shopify Cart-Permalink), der
das Produkt in den Warenkorb legt und dich sofort zur Kasse bringt.

Nur Standardbibliothek - keine Installation noetig.

Konfiguration ueber Umgebungsvariablen:
  DISCORD_WEBHOOK_URL  (Pflicht)  Webhook-Adresse aus deinem Discord-Server
  DISCORD_MENTION      (opt)      Standard "@everyone". Leer = kein Ping.
  POLL_INTERVAL        (opt, 12)  Sekunden zwischen zwei Abfragen
  MAX_RUNTIME          (opt, 0)   Laufzeit in Sekunden, 0 = unendlich
  WATCH                (opt)      Komma-Liste von Produkt-Handles.
                                  Leer = die beiden 1st-Edition-Collectors-Boxes.
                                  "ALL" = gesamter Shop (erster Lauf setzt nur
                                  die Grundlinie, alarmiert also nicht sofort).
  ALERT_COOLDOWN       (opt, 900) Sekunden, bevor fuer dieselbe Variante
                                  erneut alarmiert wird
  QUANTITY             (opt, 1)   Menge im Cart-Permalink
  STATE_FILE           (opt)      Pfad fuer Zustandsdatei
  HEARTBEAT_HOURS      (opt, 0)   Lebenszeichen alle N Stunden (0 = aus)

  TELEGRAM_BOT_TOKEN   (opt)      Nur falls du zusaetzlich Telegram willst
  TELEGRAM_CHAT_ID     (opt)
"""

import json
import os
import random
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# --------------------------------------------------------------------------
# Konfiguration
# --------------------------------------------------------------------------

SHOP = "https://saitolegends.com"
CATALOG_URL = SHOP + "/products.json?limit=250"

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
DISCORD_MENTION = os.environ.get("DISCORD_MENTION", "@everyone").strip()

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

POLL_INTERVAL = float(os.environ.get("POLL_INTERVAL", "12"))
MAX_RUNTIME = float(os.environ.get("MAX_RUNTIME", "0"))
ALERT_COOLDOWN = float(os.environ.get("ALERT_COOLDOWN", "900"))
QUANTITY = int(os.environ.get("QUANTITY", "1"))
HEARTBEAT_HOURS = float(os.environ.get("HEARTBEAT_HOURS", "0"))
STATE_FILE = os.environ.get(
    "STATE_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "saito_state.json"),
)

# Standardmaessig ueberwacht: die 1st-Edition-Boxprodukte.
DEFAULT_WATCH = {
    # 20-Pack Collectors Box (£160)
    "pre-order-sakura-winds-sl1a-20-pack-collectors-box",
    # 20-Pack Collectors Box - Drift Games Edition (£160)
    "pre-order-sakura-winds-sl1a-20-pack-collectors-box-drift-games-edition",
    # 10-Pack Booster Box (£80)
    "10-booster-box",
}

_watch_raw = os.environ.get("WATCH", "").strip()
if not _watch_raw:
    WATCH_HANDLES = set(DEFAULT_WATCH)
    WATCH_ALL = False
elif _watch_raw.upper() == "ALL":
    WATCH_HANDLES = set()
    WATCH_ALL = True
else:
    WATCH_HANDLES = {h.strip() for h in _watch_raw.split(",") if h.strip()}
    WATCH_ALL = False

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


def log(msg):
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {msg}", flush=True)


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

_ssl_ctx = ssl.create_default_context()


def _ssl_candidates():
    """Moegliche Zertifikatsquellen, in der Reihenfolge des Ausprobierens."""
    yield "Systemstandard", ssl.create_default_context()

    try:
        import certifi  # noqa: PLC0415

        yield "certifi", ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        pass

    # Typische Speicherorte auf macOS (Homebrew/LibreSSL) und Linux
    for path in (
        "/etc/ssl/cert.pem",
        "/opt/homebrew/etc/openssl@3/cert.pem",
        "/usr/local/etc/openssl@3/cert.pem",
        "/etc/ssl/certs/ca-certificates.crt",
    ):
        if os.path.exists(path):
            try:
                yield path, ssl.create_default_context(cafile=path)
            except Exception:  # noqa: BLE001
                continue


def init_ssl():
    """Sucht ein funktionierendes Zertifikatspaket.

    Auf macOS scheitert die Python-Installation von python.org haeufig mit
    CERTIFICATE_VERIFY_FAILED, weil "Install Certificates.command" nie
    ausgefuehrt wurde. Statt daran zu scheitern, probieren wir Alternativen
    durch und nehmen die erste, die funktioniert.
    """
    global _ssl_ctx  # noqa: PLW0603

    probe = "https://saitolegends.com/robots.txt"
    for name, ctx in _ssl_candidates():
        try:
            req = urllib.request.Request(probe, headers={"User-Agent": USER_AGENT})
            urllib.request.urlopen(req, timeout=10, context=ctx).read(64)
        except Exception as exc:  # noqa: BLE001
            # urllib verpackt SSL-Fehler in URLError - deshalb auspacken.
            reason = getattr(exc, "reason", None)
            is_cert_problem = isinstance(exc, ssl.SSLError) or isinstance(
                reason, ssl.SSLError
            )
            if is_cert_problem:
                log(f"   Zertifikatsquelle '{name}' funktioniert nicht.")
                continue  # naechste Quelle probieren
            # Netzwerkproblem, kein Zertifikatsproblem - Quelle akzeptieren
            _ssl_ctx = ctx
            return name
        _ssl_ctx = ctx
        return name

    log("!! Kein funktionierendes Zertifikatspaket gefunden.")
    log("!! Bitte einmal im Terminal ausfuehren:")
    log("!!   /Applications/Python*/Install\\ Certificates.command")
    log("!! Alternativ:  python3 -m pip install --upgrade certifi")
    return None


def http_get_json(url, timeout=15):
    """GET mit Cache-Buster, damit das Shopify-CDN keine alte Antwort liefert."""
    sep = "&" if "?" in url else "?"
    busted = f"{url}{sep}_t={int(time.time() * 1000)}{random.randint(100, 999)}"
    req = urllib.request.Request(
        busted,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Cache-Control": "no-cache, no-store, max-age=0",
            "Pragma": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_post_json(url, payload, timeout=15):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx) as resp:
        return resp.status, resp.read().decode("utf-8", "replace")


# --------------------------------------------------------------------------
# Benachrichtigungen
# --------------------------------------------------------------------------


def discord_send(alert, retries=3):
    """Schickt eine Nachricht an den Discord-Webhook."""
    if not DISCORD_WEBHOOK:
        return False

    if alert["kind"] == "restock":
        payload = {
            "content": (
                f"{DISCORD_MENTION} 🚨 **RESTOCK — {alert['name']}**"
                if DISCORD_MENTION
                else f"🚨 **RESTOCK — {alert['name']}**"
            ),
            "embeds": [
                {
                    "title": f"🚨 {alert['name']}",
                    "description": (
                        f"**[➡️ SOFORT IN DEN WARENKORB + CHECKOUT]"
                        f"({alert['cart_link']})**\n\n"
                        f"[Produktseite]({alert['product_link']})\n\n"
                        f"*First come, first served — nicht lange überlegen.*"
                    ),
                    "url": alert["cart_link"],
                    "color": 0xE01B24,
                    "fields": [
                        {"name": "Preis", "value": f"£{alert['price']}", "inline": True},
                        {"name": "Menge", "value": str(QUANTITY), "inline": True},
                    ],
                    "footer": {"text": "Saito Legends Restock Monitor"},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ],
            "allowed_mentions": {"parse": ["everyone"]},
        }
    else:
        payload = {
            "content": alert["text"],
            "allowed_mentions": {"parse": []},
        }

    for attempt in range(1, retries + 1):
        try:
            status, body = http_post_json(DISCORD_WEBHOOK, payload)
            if 200 <= status < 300:
                return True
            log(f"!! Discord antwortete mit {status}: {body[:200]}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:200]
            log(f"!! Discord-Fehler {exc.code}: {detail}")
            if exc.code == 429:  # Rate Limit
                time.sleep(5)
        except Exception as exc:  # noqa: BLE001
            log(f"!! Discord-Versuch {attempt}/{retries} fehlgeschlagen: {exc}")
        time.sleep(2 * attempt)
    return False


def telegram_send(alert, retries=3):
    """Optionaler Zweitkanal. Nur aktiv, wenn Token und Chat-ID gesetzt sind."""
    if not BOT_TOKEN or not CHAT_ID:
        return False

    if alert["kind"] == "restock":
        text = (
            "🚨 <b>RESTOCK — SAITO LEGENDS</b> 🚨\n\n"
            f"<b>{alert['name']}</b>\n"
            f"Preis: £{alert['price']}\n\n"
            f"➡️ <a href=\"{alert['cart_link']}\">SOFORT IN DEN WARENKORB + CHECKOUT</a>\n"
            f"ℹ️ <a href=\"{alert['product_link']}\">Produktseite</a>"
        )
    else:
        text = alert["text"]

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = urllib.parse.urlencode(
        {
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }
    ).encode()

    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                url, data=payload, headers={"User-Agent": USER_AGENT}
            )
            with urllib.request.urlopen(req, timeout=15, context=_ssl_ctx) as resp:
                if json.loads(resp.read().decode("utf-8")).get("ok"):
                    return True
        except Exception as exc:  # noqa: BLE001
            log(f"!! Telegram-Versuch {attempt}/{retries} fehlgeschlagen: {exc}")
        time.sleep(2 * attempt)
    return False


def notify(alert):
    """Verschickt ueber alle konfigurierten Kanaele. True = mindestens einer hat geklappt."""
    results = [discord_send(alert), telegram_send(alert)]
    if not any(results):
        if not DISCORD_WEBHOOK and not BOT_TOKEN:
            log("!! Kein Benachrichtigungskanal konfiguriert. Nachricht nur hier:")
            log(alert.get("text") or alert.get("name"))
        return False
    return True


def notify_text(text):
    return notify({"kind": "info", "text": text})


# --------------------------------------------------------------------------
# Zustand
# --------------------------------------------------------------------------


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"available": {}, "last_alert": {}, "last_heartbeat": 0}


def save_state(state):
    try:
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
        os.replace(tmp, STATE_FILE)
    except OSError as exc:
        log(f"!! Zustand konnte nicht gespeichert werden: {exc}")


# --------------------------------------------------------------------------
# Kernlogik
# --------------------------------------------------------------------------


def fetch_variants():
    """Liefert eine Liste von Variantendicts aus dem Shop-Katalog."""
    data = http_get_json(CATALOG_URL)
    out = []
    for product in data.get("products", []):
        handle = product.get("handle", "")
        if WATCH_HANDLES and handle not in WATCH_HANDLES:
            continue
        for variant in product.get("variants", []):
            out.append(
                {
                    "key": str(variant.get("id")),
                    "variant_id": variant.get("id"),
                    "product": product.get("title", "?"),
                    "variant": variant.get("title", ""),
                    "handle": handle,
                    "price": variant.get("price"),
                    "available": bool(variant.get("available")),
                }
            )
    return out


def build_alert(v):
    name = v["product"]
    if v["variant"] and v["variant"].lower() != "default title":
        name += f" ({v['variant']})"
    return {
        "kind": "restock",
        "name": name,
        "price": v["price"],
        "cart_link": f"{SHOP}/cart/{v['variant_id']}:{QUANTITY}",
        "product_link": f"{SHOP}/products/{v['handle']}",
    }


def run_once(state):
    """Eine Abfragerunde. Gibt die Anzahl neuer Alarme zurueck."""
    variants = fetch_variants()
    if not variants:
        log("!! Katalog leer oder WATCH-Filter trifft nichts.")
        return 0

    now = time.time()
    alerts = 0

    # Im "ALL"-Modus ist beim allerersten Lauf fast alles verfuegbar. Dann nur
    # die Grundlinie merken, statt 50 Alarme auf einmal zu feuern.
    if WATCH_ALL and not state.get("seeded"):
        for v in variants:
            state["available"][v["key"]] = v["available"]
        state["seeded"] = True
        log(f"Grundlinie gesetzt fuer {len(variants)} Varianten (kein Alarm).")
        return 0

    for v in variants:
        key = v["key"]
        was_available = state["available"].get(key)
        is_available = v["available"]

        became_available = is_available and was_available is not True
        cooldown_over = (now - state["last_alert"].get(key, 0)) > ALERT_COOLDOWN

        if became_available and cooldown_over:
            log(f">>> RESTOCK: {v['product']} / {v['variant']}")
            if notify(build_alert(v)):
                state["last_alert"][key] = now
                alerts += 1
            else:
                # Versand fehlgeschlagen - beim naechsten Durchlauf erneut versuchen
                state["available"][key] = was_available
                continue

        if was_available is True and not is_available:
            log(f"    wieder ausverkauft: {v['product']}")

        state["available"][key] = is_available

    return alerts


def startup_report():
    """Holt den Katalog einmal und beschreibt, was ueberwacht wird.

    Gibt (Konsolenzeilen, Discord-Text) zurueck. Bei einem Fehler wird nur
    gemeldet, dass der Abruf nicht geklappt hat - der Monitor laeuft trotzdem.
    """
    try:
        variants = fetch_variants()
    except Exception as exc:  # noqa: BLE001
        msg = f"Katalog beim Start nicht abrufbar ({exc}). Monitor laeuft trotzdem."
        return [msg], f"⚠️ {msg}"

    lines = []
    parts = []

    if WATCH_ALL:
        verfuegbar = sum(1 for v in variants if v["available"])
        lines.append(
            f"Ueberwacht: gesamter Shop - {len(variants)} Varianten "
            f"({verfuegbar} aktuell verfuegbar)"
        )
        parts.append(
            f"**Gesamter Shop** — {len(variants)} Varianten, "
            f"davon {verfuegbar} aktuell verfügbar."
        )
    else:
        lines.append(f"Ueberwacht werden {len(variants)} Variante(n):")
        for v in variants:
            name = v["product"]
            if v["variant"] and v["variant"].lower() != "default title":
                name += f" ({v['variant']})"
            status = "AUF LAGER" if v["available"] else "ausverkauft"
            lines.append(f"  - {name} — £{v['price']} — {status}")
            symbol = "🟢" if v["available"] else "🔴"
            parts.append(f"{symbol} **{name}** — £{v['price']}")

        # Handles, die im Shop gar nicht existieren, sind fast immer Tippfehler
        gefunden = {v["handle"] for v in variants}
        for fehlend in sorted(WATCH_HANDLES - gefunden):
            lines.append(f"  ! Handle nicht im Shop gefunden: {fehlend}")
            parts.append(f"⚠️ Handle nicht gefunden: `{fehlend}`")

    return lines, "\n".join(parts)


def main():
    if not DISCORD_WEBHOOK and not BOT_TOKEN:
        log("WARNUNG: DISCORD_WEBHOOK_URL fehlt.")
        log("Der Monitor laeuft, meldet Treffer aber nur auf der Konsole.")

    state = load_state()
    started = time.time()

    log(f"Monitor gestartet. Intervall {POLL_INTERVAL}s.")

    cert_source = init_ssl()
    if cert_source:
        log(f"TLS-Zertifikate: {cert_source}")

    console_lines, discord_list = startup_report()
    for line in console_lines:
        log(line)

    if "--quiet-start" not in sys.argv:
        notify_text(
            "✅ **Saito-Legends-Monitor läuft.**\n"
            f"Prüfe alle {int(POLL_INTERVAL)} Sekunden auf Restocks.\n\n"
            "**Überwacht:**\n"
            f"{discord_list}"
        )

    consecutive_errors = 0

    while True:
        loop_start = time.time()
        try:
            run_once(state)
            consecutive_errors = 0
        except urllib.error.HTTPError as exc:
            consecutive_errors += 1
            log(f"!! HTTP {exc.code} beim Abruf (Fehler #{consecutive_errors})")
        except Exception as exc:  # noqa: BLE001
            consecutive_errors += 1
            log(f"!! Fehler: {exc!r} (Fehler #{consecutive_errors})")

        if consecutive_errors == 20:
            notify_text(
                "⚠️ **Monitor-Warnung:** 20 Abfragen in Folge fehlgeschlagen."
            )

        now = time.time()

        if HEARTBEAT_HOURS > 0:
            if now - state.get("last_heartbeat", 0) > HEARTBEAT_HOURS * 3600:
                state["last_heartbeat"] = now
                notify_text(
                    "💚 Monitor laeuft weiterhin. "
                    f"Laufzeit: {int((now - started) / 60)} Min."
                )

        save_state(state)

        if MAX_RUNTIME > 0 and (now - started) >= MAX_RUNTIME:
            log("Maximale Laufzeit erreicht - sauberer Ausstieg.")
            return 0

        if consecutive_errors:
            delay = min(POLL_INTERVAL * (2 ** min(consecutive_errors, 5)), 300)
        else:
            delay = POLL_INTERVAL + random.uniform(-1.5, 1.5)

        time.sleep(max(1.0, delay - (time.time() - loop_start)))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("Abgebrochen.")
        sys.exit(0)
