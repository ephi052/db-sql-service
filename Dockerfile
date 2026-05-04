FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Create non-root user
RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /srv

COPY requirments.txt /srv/requirments.txt

RUN pip install --no-cache-dir --upgrade pip \
        && pip install --no-cache-dir -r /srv/requirments.txt

COPY app/ /srv/app/

# Data directory for SQLite (mounted as volume)
RUN mkdir -p /data && chown -R app:app /data /srv

USER app

EXPOSE 8000

# proxy headers flags are recommended when behind Nginx proxy
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
