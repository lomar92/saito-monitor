# Saito Legends Restock Monitor

Monitors the Shopify store at [saitolegends.com](https://saitolegends.com) and instantly sends a Discord notification with a direct checkout link as soon as a tracked product comes back in stock.

---

## How it works

The script polls the public Shopify API (`/products.json`) every 12 seconds and compares the stock status against the last saved state. When a variant switches from "out of stock" to "available", a Discord ping is sent immediately with a link that places the product directly into the cart.

---

## Setup

### 1. Discord Webhook

1. Open Discord → Create your own server (private, just for you)
2. Channel → **Edit Channel** → **Integrations** → **Webhooks** → **New Webhook**
3. Copy the webhook URL

### 2. Add GitHub Secret

**Settings → Secrets and variables → Actions → New repository secret**

| Name | Value |
|---|---|
| `DISCORD_WEBHOOK_URL` | your copied webhook URL |

### 3. Set Workflow Permissions

**Settings → Actions → General → Workflow permissions → Read and write permissions → Save**

Without this the monitor cannot restart itself.

### 4. Start the Monitor

**Actions → Saito Legends Restock Monitor → Run workflow → Run workflow**

---

## Adjusting Parameters

All settings are in `.github/workflows/saito-monitor.yml` under the `env:` section.

```yaml
- name: Start monitor
  env:
    DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
    DISCORD_MENTION: "@everyone"
    POLL_INTERVAL: "12"
    MAX_RUNTIME: "20400"
    ALERT_COOLDOWN: "180"
    QUANTITY: "2"           # ← quantity in the checkout link
    HEARTBEAT_HOURS: "0"
    STATUS_EVERY: "300"
    STATE_FILE: saito_state.json
    WATCH: ${{ inputs.watch }}   # ← empty = the 3 default products
```

### Changing Products (`WATCH`)

By default these 3 products are monitored (defined in `saito_monitor.py` under `DEFAULT_WATCH`):

```
pre-order-sakura-winds-sl1a-20-pack-collectors-box
pre-order-sakura-winds-sl1a-20-pack-collectors-box-drift-games-edition
10-booster-box
```

The handle of a product is found in the shop URL:
`saitolegends.com/products/`**`the-handle-is-here`**

**Watch a single product** — add to `env:` in the workflow file:
```yaml
WATCH: "acrylic-slab-display-case"
```

**Watch multiple products** (comma-separated):
```yaml
WATCH: "product-handle-1,product-handle-2"
```

**Watch the entire shop:**
```yaml
WATCH: "ALL"
```
> The first run only sets the baseline and does not alert immediately.

To permanently change the default products, edit the `DEFAULT_WATCH` list in `saito_monitor.py` (line 73).

### Changing Quantity (`QUANTITY`)

Controls how many units the checkout link adds to the cart.

```yaml
QUANTITY: "2"   # checkout link adds 2 units to the cart
```

### All Available Parameters

| Variable | Default | Description |
|---|---|---|
| `DISCORD_WEBHOOK_URL` | — | Webhook URL (required, store as secret) |
| `DISCORD_MENTION` | `@everyone` | Ping in alert. Empty = no ping |
| `POLL_INTERVAL` | `12` | Seconds between requests |
| `WATCH` | 3 default products | Comma-list of product handles or `ALL` |
| `QUANTITY` | `2` | Quantity in the direct checkout link |
| `ALERT_COOLDOWN` | `180` | Seconds before re-alerting for the same product |
| `MAX_RUNTIME` | `20400` | Runtime in seconds (5h40m), then clean restart |
| `HEARTBEAT_HOURS` | `0` | Liveness ping to Discord every N hours (0 = off) |
| `STATUS_EVERY` | `300` | Status line in Actions log every N seconds (not Discord) |
| `TELEGRAM_BOT_TOKEN` | — | Optional: Telegram as second notification channel |
| `TELEGRAM_CHAT_ID` | — | Optional: Telegram as second notification channel |

---

## Testing Notifications

Click **Run workflow** in the Actions tab and enter the handle of an available product in the **watch** field, e.g.:

```
acrylic-slab-display-case
```

The test run monitors only that product, runs for 60 seconds, does **not** restart itself, and fires a Discord alert immediately since there is no saved state.

---

## Stopping the Monitor

Click **Cancel** on the active workflow run in the Actions tab. The monitor does **not** restart when manually cancelled — only after a normal exit (5h40m) or an error.

---

## 24/7 Operation Without a Public Repository

GitHub Actions only gives **2,000 free minutes/month** for private repos. This monitor uses ~1,360 minutes/day, exhausting the limit in ~1.5 days. Three alternatives:

### Option 1: Self-hosted Runner (free, recommended)

Register your own runner on any device (Raspberry Pi, old laptop, NAS, VPS):

**Settings → Actions → Runners → New self-hosted runner** → follow the instructions.

Then change one line in the workflow file:

```yaml
runs-on: self-hosted   # instead of ubuntu-latest
```

No minute limits, runs on your own hardware, completely free.

### Option 2: Docker on Fly.io (free, no local device needed)

A `Dockerfile` is already included. Fly.io offers a free tier that is sufficient for this use case:

```bash
# Install Fly CLI: https://fly.io/docs/hands-on/install-flyctl/
fly launch --no-deploy
fly secrets set DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
fly volumes create saito_data --size 1
fly deploy
```

The state is stored in the volume at `/data/saito_state.json` and survives restarts.

### Option 3: Railway

Alternative to Fly.io — also Docker-based, free tier available:

1. [railway.app](https://railway.app) → New Project → Deploy from GitHub Repo
2. Set environment variable `DISCORD_WEBHOOK_URL`
3. Mount a volume at `/data` for state persistence

### Option 4: GitHub Pro ($4/month)

3,000 free minutes — enough for ~2 days of continuous operation, still not sufficient for true 24/7 use.

---

## Running Locally (for testing)

```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
python3 saito_monitor.py
```

With `--quiet-start` no startup message is sent to Discord:

```bash
python3 saito_monitor.py --quiet-start
```

Stop with **Ctrl+C**.

---

## Project Structure

```
saito_monitor.py                    # Entire application, Python stdlib only
.github/workflows/saito-monitor.yml # GitHub Actions workflow
Dockerfile                          # For Fly.io / Railway / local Docker
ANLEITUNG.md                        # Detailed step-by-step guide (German)
```
