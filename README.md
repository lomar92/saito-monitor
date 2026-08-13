# Saito Legends Restock Monitor

Überwacht den Shopify-Shop von [saitolegends.com](https://saitolegends.com) und schickt sofort eine Discord-Benachrichtigung mit Checkout-Direktlink, sobald ein überwachtes Produkt wieder auf Lager geht.

---

## Wie es funktioniert

Das Skript fragt alle 12 Sekunden die öffentliche Shopify-API (`/products.json`) ab und vergleicht den Lagerstatus mit dem zuletzt gespeicherten Zustand. Wechselt eine Variante von „ausverkauft" auf „verfügbar", kommt sofort ein Discord-Ping mit einem Link der das Produkt direkt in den Warenkorb legt.

---

## Einrichtung

### 1. Discord-Webhook

1. Discord öffnen → Eigenen Server anlegen (privat, nur für dich)
2. Kanal → **Kanal bearbeiten** → **Integrationen** → **Webhooks** → **Neuer Webhook**
3. Webhook-URL kopieren

### 2. GitHub-Secret hinterlegen

**Settings → Secrets and variables → Actions → New repository secret**

| Name | Wert |
|---|---|
| `DISCORD_WEBHOOK_URL` | deine kopierte Webhook-URL |

### 3. Workflow-Berechtigungen setzen

**Settings → Actions → General → Workflow permissions → Read and write permissions → Save**

Ohne das kann sich der Monitor nicht selbst neu starten.

### 4. Monitor starten

**Actions → Saito Legends Restock Monitor → Run workflow → Run workflow**

---

## Parameter anpassen

Alle Einstellungen befinden sich in `.github/workflows/saito-monitor.yml` unter dem Abschnitt `env:`.

```yaml
- name: Monitor starten
  env:
    DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
    DISCORD_MENTION: "@everyone"
    POLL_INTERVAL: "12"
    MAX_RUNTIME: "20400"
    ALERT_COOLDOWN: "900"
    QUANTITY: "2"           # ← Menge im Checkout-Link
    HEARTBEAT_HOURS: "0"
    STATUS_EVERY: "300"
    STATE_FILE: saito_state.json
    WATCH: ${{ inputs.watch }}   # ← leer = die 3 Standard-Artikel
```

### Produkte ändern (`WATCH`)

Standardmäßig werden diese 3 Artikel überwacht (in `saito_monitor.py` unter `DEFAULT_WATCH`):

```
pre-order-sakura-winds-sl1a-20-pack-collectors-box
pre-order-sakura-winds-sl1a-20-pack-collectors-box-drift-games-edition
10-booster-box
```

Den Handle eines Artikels findest du in der Shop-URL:
`saitolegends.com/products/`**`der-handle-steht-hier`**

**Einzelnen Artikel überwachen** — in der Workflow-Datei unter `env:` eintragen:
```yaml
WATCH: "acrylic-slab-display-case"
```

**Mehrere Artikel** (kommagetrennt):
```yaml
WATCH: "artikel-handle-1,artikel-handle-2"
```

**Gesamten Shop überwachen:**
```yaml
WATCH: "ALL"
```
> Der erste Lauf setzt dabei nur die Grundlinie und alarmiert nicht sofort.

Um die Standard-Artikel dauerhaft zu ändern, die Liste in `saito_monitor.py` bei `DEFAULT_WATCH` (Zeile 73) bearbeiten.

### Menge ändern (`QUANTITY`)

Bestimmt wie viele Stück des Artikels der Checkout-Link in den Warenkorb legt.

```yaml
QUANTITY: "2"   # Checkout-Link legt 2 Stück in den Warenkorb
```

### Alle verfügbaren Parameter

| Variable | Standard | Bedeutung |
|---|---|---|
| `DISCORD_WEBHOOK_URL` | — | Webhook-URL (Pflicht, als Secret) |
| `DISCORD_MENTION` | `@everyone` | Ping im Alarm. Leer = kein Ping |
| `POLL_INTERVAL` | `12` | Sekunden zwischen zwei Abfragen |
| `WATCH` | 3 Standard-Artikel | Komma-Liste von Produkt-Handles oder `ALL` |
| `QUANTITY` | `2` | Menge im Checkout-Direktlink |
| `ALERT_COOLDOWN` | `900` | Sekunden Sperrzeit vor erneutem Alarm für dasselbe Produkt |
| `MAX_RUNTIME` | `20400` | Laufzeit in Sekunden (5h40m), dann sauberer Neustart |
| `HEARTBEAT_HOURS` | `0` | Lebenszeichen-Ping an Discord alle N Stunden (0 = aus) |
| `STATUS_EVERY` | `300` | Statuszeile im Actions-Log alle N Sekunden (nicht Discord) |
| `TELEGRAM_BOT_TOKEN` | — | Optional: Telegram als Zweitkanal |
| `TELEGRAM_CHAT_ID` | — | Optional: Telegram als Zweitkanal |

---

## Notification testen

Im Workflow-Tab auf **Run workflow** klicken und im Feld **watch** einen Handle eines verfügbaren Artikels eingeben, z. B.:

```
acrylic-slab-display-case
```

Der Testlauf überwacht nur diesen Artikel, läuft 60 Sekunden, startet sich danach **nicht** selbst neu und schickt sofort einen Discord-Alarm da kein gespeicherter State vorhanden ist.

---

## Monitor stoppen

Im Actions-Tab den laufenden Workflow-Run **Cancel** klicken. Der Monitor startet sich **nicht** neu wenn er manuell gecancelt wird — nur bei normalem Ende (5h40m) oder Fehler.

---

## 24/7-Betrieb ohne öffentliches Repository

GitHub Actions gibt für **private** Repos nur 2.000 Freiminuten/Monat. Dieser Monitor verbraucht ~1.360 Minuten/Tag, was das Limit in ~1,5 Tagen erschöpft. Drei Alternativen:

### Option 1: Self-hosted Runner (kostenlos, empfohlen)

Einen eigenen Runner auf einem Gerät registrieren (Raspberry Pi, alter Laptop, NAS, VPS):

**Settings → Actions → Runners → New self-hosted runner** → Anleitung folgen.

Danach in der Workflow-Datei eine Zeile ändern:

```yaml
runs-on: self-hosted   # statt ubuntu-latest
```

Kein Minutenlimit, läuft auf eigener Hardware, komplett kostenlos.

### Option 2: Docker auf Fly.io (kostenlos, kein lokales Gerät nötig)

Ein `Dockerfile` liegt bereits im Repo. Fly.io bietet ein kostenloses Tier das für diesen Use-Case ausreicht:

```bash
# Fly CLI installieren: https://fly.io/docs/hands-on/install-flyctl/
fly launch --no-deploy
fly secrets set DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
fly volumes create saito_data --size 1
fly deploy
```

Der State wird im Volume unter `/data/saito_state.json` gespeichert und überlebt Neustarts.

### Option 3: Railway

Alternativ zu Fly.io — ebenfalls Docker-basiert, kostenloses Tier vorhanden:

1. [railway.app](https://railway.app) → New Project → Deploy from GitHub Repo
2. Environment Variable `DISCORD_WEBHOOK_URL` setzen
3. Volume unter `/data` einbinden für State-Persistenz

### Option 4: GitHub Pro ($4/Monat)

3.000 Freiminuten — reicht für ~2 Tage Dauerbetrieb, also immer noch zu wenig für echten 24/7-Betrieb.

---

## Lokaler Betrieb (zum Testen)

```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
python3 saito_monitor.py
```

Mit `--quiet-start` wird keine Startmeldung an Discord geschickt:

```bash
python3 saito_monitor.py --quiet-start
```

Stoppen mit **Strg+C**.

---

## Projektstruktur

```
saito_monitor.py                    # Gesamte Anwendung, nur Python-Stdlib
.github/workflows/saito-monitor.yml # GitHub Actions Workflow
Dockerfile                          # Für Fly.io / Railway / lokalen Docker
ANLEITUNG.md                        # Ausführliche Schritt-für-Schritt-Anleitung
```
