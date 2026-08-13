# Alternative zu GitHub Actions: Dauerbetrieb auf Fly.io / Railway / Render.
FROM python:3.12-slim

WORKDIR /app
COPY saito_monitor.py .

# DISCORD_WEBHOOK_URL wird als Secret gesetzt, nicht hier.
ENV POLL_INTERVAL=12 \
    DISCORD_MENTION=@everyone \
    ALERT_COOLDOWN=900 \
    HEARTBEAT_HOURS=12 \
    STATE_FILE=/data/saito_state.json \
    PYTHONUNBUFFERED=1

VOLUME ["/data"]

CMD ["python", "saito_monitor.py"]
