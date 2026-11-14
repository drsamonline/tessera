# TESSERA reference core.
#
# No dependencies, so the image is a Python base and the source: no build stage,
# no lockfile, nothing to pin but the interpreter.
FROM python:3.12-slim

LABEL org.opencontainers.image.title="tessera" \
      org.opencontainers.image.description="The mosaic layer above every CRM - reference core" \
      org.opencontainers.image.source="https://github.com/drsamonline/tessera" \
      org.opencontainers.image.licenses="PolyForm-Noncommercial-1.0.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TESSERA_HOST=0.0.0.0 \
    TESSERA_PORT=8080

WORKDIR /app
COPY tessera/ ./tessera/
COPY VERSION ./

# non-root, and the process cannot write anywhere except /tmp
RUN useradd --create-home --uid 10001 tessera \
 && chown -R tessera:tessera /app
USER 10001

EXPOSE 8080

# A healthcheck that fails loudly is worth more than one that always passes: this
# one is a real request to a real route.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2).status == 200 else 1)"

ENTRYPOINT ["python3", "-m", "tessera.api"]
