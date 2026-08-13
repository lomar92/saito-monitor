# Saito Legends — Restock-Monitor + Gmail-Setup

Zwei Dinge, unabhängig voneinander nutzbar:

1. **Restock-Monitor** — überwacht den Shop und schickt dir in Sekunden eine Discord-Nachricht mit Checkout-Direktlink.
2. **Gmail-Regel** — sortiert und markiert alle Mails von Saito Legends.

Gesamter Zeitaufwand: etwa 15 Minuten. Du brauchst keine Programmierkenntnisse, nur Kopieren und Einfügen.

---

## Teil 1: Discord vorbereiten (5 Minuten)

Das Skript braucht eine Adresse, an die es die Nachricht schicken kann. Diese Adresse heißt **Webhook** und holst du dir aus Discord. Am Computer geht das leichter als am Handy.

### 1.1 Eigenen Server anlegen

Das ist ein privater Bereich nur für dich — nicht der Saito-Legends-Server, und niemand sonst sieht ihn.

1. Discord öffnen.
2. In der linken Leiste ganz unten auf das **runde Plus-Symbol** klicken („Server hinzufügen").
3. **Eigenen erstellen** wählen.
4. Bei der Frage nach dem Zweck: **Nur für mich und meine Freunde**.
5. Namen vergeben, z. B. `Meine Alarme` → **Erstellen**.

Du landest in einem neuen Server mit einem Kanal namens `#allgemein`. Der reicht.

### 1.2 Webhook erstellen

1. Fahre mit der Maus über den Kanal **`#allgemein`** in der Kanalliste.
2. Klicke auf das **Zahnrad-Symbol**, das rechts daneben erscheint („Kanal bearbeiten").
3. Links im Menü auf **Integrationen**.
4. Auf **Webhooks** klicken, dann auf **Neuer Webhook**.
5. Es erscheint ein Eintrag namens „Spidey Bot" o. ä. Klicke ihn an — du kannst ihn umbenennen, z. B. in `Saito Alarm`.
6. Auf **Webhook-URL kopieren** klicken.

In deiner Zwischenablage liegt jetzt eine lange Adresse, die so aussieht:

```
https://discord.com/api/webhooks/1234567890123456/AbCdEf-lange_zufaellige_zeichenkette
```

**Das ist dein `DISCORD_WEBHOOK_URL`.** Speichere sie dir kurz irgendwo zwischen (Notizen-App).

> 🔒 Behandle die Adresse wie ein Passwort. Wer sie hat, kann in deinen Kanal schreiben. Poste sie nirgends öffentlich.

### 1.3 Sicherstellen, dass der Ping durchkommt

Der Alarm enthält ein `@everyone` — in deinem eigenen Server bist nur du das, also klingelt es garantiert.

1. **Rechtsklick auf den Servernamen** → **Benachrichtigungseinstellungen**.
2. **Alle Nachrichten** auswählen.
3. Das Häkchen bei **@everyone und @here unterdrücken** muss **aus** sein.

Auf dem Handy zusätzlich: Discord-App → Servereinstellungen → Benachrichtigungen → sicherstellen, dass Push aktiv ist. Und prüfe in den Handy-Systemeinstellungen, dass Discord nicht vom Energiesparmodus eingeschränkt wird.

---

## Teil 2: Sofort testen (2 Minuten)

Bevor wir das Ganze in die Cloud stellen, prüfen wir am Mac, ob die Nachricht ankommt. Terminal öffnen (Cmd+Leertaste → „Terminal") und diese drei Zeilen eingeben. In der ersten Zeile deine kopierte Adresse zwischen die Anführungszeichen setzen:

```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/DEINE/ADRESSE"
cd ~/Downloads          # oder wohin du saito_monitor.py gelegt hast
python3 saito_monitor.py
```

Innerhalb weniger Sekunden sollte in deinem Discord-Kanal stehen: *„✅ Saito-Legends-Monitor läuft."*

Kommt die Nachricht an, ist alles richtig. Mit **Strg+C** beenden.

Kommt nichts an, steht im Terminal eine Fehlermeldung — schick sie mir, dann schaue ich.

### Falls `CERTIFICATE_VERIFY_FAILED` erscheint

Häufig auf dem Mac. Python-Installationen von python.org richten ihr Zertifikatspaket nicht automatisch ein, dadurch traut dein Python keiner verschlüsselten Verbindung — weder zu Discord noch zum Shop.

Das Skript sucht sich inzwischen selbst eine funktionierende Zertifikatsquelle und meldet beim Start, welche es nimmt (`TLS-Zertifikate: ...`). In den meisten Fällen läuft es damit einfach durch.

Falls doch nicht, einmal im Terminal ausführen — die Versionsnummer ggf. anpassen:

```bash
/Applications/Python\ 3.12/Install\ Certificates.command
```

Den passenden Ordnernamen findest du mit `ls /Applications | grep Python`. Alternative, funktioniert immer:

```bash
python3 -m pip install --upgrade certifi
```

---

## Teil 3: 24/7-Betrieb über GitHub Actions (8 Minuten)

Der Monitor soll auch laufen, wenn dein Mac aus ist. Für **öffentliche** GitHub-Repos sind die Rechenminuten unbegrenzt, das kostet also nichts.

1. Konto auf [github.com](https://github.com) anlegen, falls noch nicht vorhanden.
2. Neues **öffentliches** Repository anlegen (z. B. `saito-monitor`).
3. Diese Dateien hochladen — die Ordnerstruktur muss exakt so bleiben:

   ```
   saito_monitor.py
   .github/workflows/saito-monitor.yml
   ```

   Beim Upload über die Weboberfläche legst du den Ordner an, indem du beim Dateinamen `.github/workflows/saito-monitor.yml` eintippst — die Schrägstriche erzeugen die Ordner automatisch.

4. **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `DISCORD_WEBHOOK_URL`
   - Secret: deine kopierte Webhook-Adresse
   - **Add secret**

5. **Settings → Actions → General** → ganz unten bei *Workflow permissions* auf **„Read and write permissions"** stellen → **Save**. Ohne das kann sich der Lauf nicht selbst neu starten.

6. Tab **Actions** → links *Saito Legends Restock Monitor* → rechts **Run workflow** → **Run workflow**.

Nach etwa einer Minute kommt die Startmeldung in deinen Discord-Kanal. Ab dann läuft es.

**Wie es dauerhaft läuft:** Ein GitHub-Lauf darf maximal 6 Stunden dauern. Der Monitor läuft deshalb 5 Stunden 40 Minuten und startet sich danach selbst neu. Zusätzlich springt alle 3 Stunden ein Zeitplan an, falls ein Lauf abstürzt. Alle 12 Stunden bekommst du ein kurzes Lebenszeichen — bleibt das aus, ist etwas kaputt.

> ⚠️ GitHub schaltet Zeitplan-Abläufe nach **60 Tagen ohne Aktivität im Repo** ab. Für die nächsten Wochen kein Thema; wenn es länger läuft, ab und zu eine Kleinigkeit im Repo ändern.

### Alternative ohne GitHub

Wenn dir das zu umständlich ist, liegt ein `Dockerfile` bei, mit dem der Monitor bei Fly.io oder Railway läuft:

```bash
fly launch --no-deploy
fly secrets set DISCORD_WEBHOOK_URL="..."
fly volumes create data --size 1
fly deploy
```

---

## Teil 4: Was passiert im Alarmfall

In deinem Discord-Kanal erscheint mit `@everyone`-Ping eine rot markierte Karte:

> 🚨 **SL1A 1st Edition 20-Pack Collectors Box**
> Preis: £160.00 · Menge: 1
> **➡️ SOFORT IN DEN WARENKORB + CHECKOUT**

Der Link ist ein Shopify-Cart-Permalink (`saitolegends.com/cart/VARIANTEN-ID:1`). Ein Tap legt die Box in den Warenkorb und öffnet direkt die Kasse — Produktseite und Warenkorb werden komplett übersprungen.

**Damit du wirklich in unter 15 Sekunden durch bist — das ist der wichtigste Teil:**

- Lege dir **jetzt** ein Kundenkonto im Shop an und logge dich auf dem Handy ein, damit Adresse und Mail hinterlegt sind.
- Aktiviere **Shop Pay** oder **Apple Pay**. Beides akzeptiert der Shop und spart die komplette Formulareingabe.
- Mach einmal einen **Testkauf mit einem billigen Artikel** (ein Sticker für ein paar Pfund). Danach sind deine Daten gespeichert und du kennst den Ablauf. Das bringt mehr Zeitgewinn als jede Einstellung am Skript.

---

## Teil 5: Gmail einrichten (2 Minuten)

Das musst du von Hand machen — Gmail-Filter lassen sich grundsätzlich nicht automatisiert anlegen.

1. Gmail öffnen → in die Suchleiste klicken → rechts auf das **Schieberegler-Symbol** („Suchoptionen anzeigen").
2. Ins Feld **Von** eintragen:

   ```
   saitolegends.com OR hello@saitolegends.com
   ```

3. Unten auf **Filter erstellen** klicken.
4. Diese Häkchen setzen:
   - ✅ **Label anwenden** → *Neues Label* → `Saito Legends`
   - ✅ **Immer als wichtig markieren**
   - ✅ **Markieren** (Stern)
   - ❌ **Posteingang überspringen** — dieses Häkchen **nicht** setzen, sonst landen die Mails nicht im Posteingang.
   - ✅ **Filter auch auf passende Konversationen anwenden**
5. **Filter erstellen**.

**Push aufs Handy:** Gmail-App → Einstellungen → dein Konto → **Benachrichtigungen für Labels** → `Saito Legends` → aktivieren, Ton auf laut. Damit klingelt es auch bei der offiziellen Restock-Mail des Shops.

Deine Adresse `amarlojo@gmail.com` steht bereits auf der Warteliste — die Bestätigungsmail vom 13.08. liegt im Postfach. Der Monitor bleibt trotzdem sinnvoll: die Shop-Mail geht gleichzeitig an rund 1.000 Leute raus und hat oft mehrere Minuten Verzögerung. Der Monitor schaut direkt an der Quelle nach.

---

## Einstellungen anpassen

Alles über Umgebungsvariablen (in der Workflow-Datei unter `env:`):

| Variable | Standard | Bedeutung |
|---|---|---|
| `DISCORD_WEBHOOK_URL` | — | Deine Webhook-Adresse (Pflicht) |
| `DISCORD_MENTION` | `@everyone` | Ping im Alarm. Leer lassen = kein Ping |
| `POLL_INTERVAL` | `12` | Sekunden zwischen zwei Abfragen |
| `WATCH` | die 2 Collectors Boxes | Komma-Liste von Produkt-Handles, oder `ALL` für den ganzen Shop |
| `QUANTITY` | `1` | Menge im Checkout-Link |
| `ALERT_COOLDOWN` | `900` | Sperrzeit in Sekunden, bevor für dasselbe Produkt erneut alarmiert wird |
| `HEARTBEAT_HOURS` | `12` | Lebenszeichen-Intervall, `0` = aus |

**`WATCH=ALL`** wird interessant, sobald es um die **Unlimited-Edition** geht: dann erkennt der Monitor auch völlig neu eingestellte Produkte. Der erste Lauf setzt dabei nur die Grundlinie und alarmiert nicht.

Telegram lässt sich jederzeit als Zweitkanal dazuschalten (`TELEGRAM_BOT_TOKEN` und `TELEGRAM_CHAT_ID` setzen) — der Code kann beides parallel.

---

## Warum kein Auto-Kauf

Ein Bot, der selbstständig mit hinterlegter Karte durch den Checkout geht, ist bewusst nicht dabei:

- Er verstößt gegen die Nutzungsbedingungen des Shops — bei einem Community-Projekt mit aktivem Discord ist eine Kontosperre ein reales Risiko.
- Shopify-Checkouts sind bot-geschützt (Captcha, Rate Limits, Checkout-Tokens). Solche Skripte brechen bei jeder Änderung am Shop.
- Er müsste deine Zahlungsdaten im Klartext speichern.

Alarm + Cart-Permalink + gespeicherte Zahlungsmethode bringt dich praktisch genauso schnell durch. Bei 10–30 Boxen entscheiden Sekunden, nicht Millisekunden.

## Fairness-Hinweis

`POLL_INTERVAL=12` sind fünf Abfragen pro Minute auf einen öffentlichen, für genau diesen Zweck gedachten Endpunkt. Das ist unproblematisch. Geh nicht unter 5 Sekunden — das belastet den Shop unnötig und kann dazu führen, dass deine IP blockiert wird. Dann stehst du schlechter da als vorher.
