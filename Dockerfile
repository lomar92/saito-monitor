# Dauerbetrieb auf Fly.io / Railway / Render.
# Zwei Prozesse moeglich: saito_monitor.py (Restock) + inventory_tracker.py (Bestandsaenderungen)
FROM python:3.12-slim

WORKDIR /app
COPY saito_monitor.py inventory_tracker.py ./

ENV POLL_INTERVAL=12 \
    DISCORD_MENTION=@everyone \
    ALERT_COOLDOWN=180 \
    HEARTBEAT_HOURS=0 \
    STATE_FILE=/data/saito_state.json \
    PYTHONUNBUFFERED=1

VOLUME ["/data"]

CMD ["python", "saito_monitor.py"]
