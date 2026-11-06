# Converter image: Python app + Java + DITA-OT. Build, then run behind your SSO reverse proxy.
FROM python:3.13-slim

ARG DITA_OT_VERSION=4.3.4
RUN apt-get update && apt-get install -y --no-install-recommends default-jre-headless unzip curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL -o /tmp/dita-ot.zip https://github.com/dita-ot/dita-ot/releases/download/${DITA_OT_VERSION}/dita-ot-${DITA_OT_VERSION}.zip \
    && unzip -q /tmp/dita-ot.zip -d /opt && rm /tmp/dita-ot.zip \
    && ln -s /opt/dita-ot-${DITA_OT_VERSION} /opt/dita-ot

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ixia2md ./ixia2md

ENV DITA_OT_HOME=/opt/dita-ot OUTPUT_ROOT=/data/runs
RUN useradd -m app && mkdir -p /data/runs && chown -R app /data
USER app
EXPOSE 8080
# Secrets (CCMS_URL, CCMS_USER, CCMS_PASSWORD) arrive as environment variables from your secret manager.
CMD ["python", "-m", "ixia2md.app", "--host", "0.0.0.0", "--port", "8080"]
