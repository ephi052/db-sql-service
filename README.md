# DB SQL Service

Small FastAPI service for ingesting JSON events into SQLite and storing uploaded images.

## Configuration

Environment variables:

- `API_KEY`: required value for the `X-API-Key` header on protected endpoints.
- `DATABASE_URL`: SQLAlchemy database URL. Defaults to `sqlite:////data/app.db`.
- `IMAGES_DIR`: directory where uploaded files are stored. Defaults to `/data/images`.
- `MAX_IMAGE_BYTES`: maximum accepted image size in bytes. Defaults to `1048576`.
- `ALLOWED_IPS`: comma-separated allowlist for mutating endpoints such as `POST /v1/events`, `POST /v1/images`, and `DELETE /v1/images/{image_id}`. Supports single IPs and CIDR ranges. Defaults to allow none unless explicitly configured.
- `DEMO_MODE`: when set to `true`, bypasses the image/event mutating IP allowlist checks for local demos. Defaults to `false`.

## Proxy Trust

The service is typically deployed behind Nginx. The app reads the client IP from `X-Forwarded-For`, then `X-Real-IP`, then the direct socket address. Keep your reverse proxy configured to pass those headers and only trust proxy addresses you control.

If you are exposing the service through another proxy or tunnel, make sure that proxy forwards the real client IP correctly; otherwise the allowlist will evaluate the proxy IP instead of the caller.

## Endpoints

### Events

`POST /v1/events`

- Requires `X-API-Key` and an allowed IP unless `DEMO_MODE=true`.
- Body must include `payload.stid`, `payload.exnum`, and `payload.table`.

`GET /v1/events`

- Requires `X-API-Key`.
- Supports `limit` and `offset`.

`GET /v1/events/{event_id}?exnum=...`

- Requires `X-API-Key`.
- Returns `404` when the id does not exist or the `exnum` does not match.

### Images

`POST /v1/images`

- Requires `X-API-Key` and an allowed IP unless `DEMO_MODE=true`.
- Accepts multipart form field `file`.
- File `Content-Type` must start with `image/`.
- The original filename must include an extension and must not contain path separators.
- The file must be no larger than `MAX_IMAGE_BYTES`.
- Returns `201`:

```json
{
  "image_id": 1,
  "image_url": "https://example.com/v1/images/1"
}
```

`GET /v1/images/{image_id}`

- Public endpoint; no API key required.
- Streams the image using the stored content type.
- Returns `404` for unknown or missing images.

`DELETE /v1/images/{image_id}`

- Requires `X-API-Key` and an allowed IP unless `DEMO_MODE=true`.
- Returns `204` on success and `404` when the image id does not exist.
- Uses the same IP policy as `POST /v1/events` and `POST /v1/images`.

## Examples

```bash
curl -H "X-API-Key: $API_KEY" \
  -F "file=@plot.png;type=image/png" \
  http://localhost/v1/images
```

```bash
curl -H "X-API-Key: $API_KEY" \
  -H "X-Forwarded-For: 10.0.0.1" \
  -F "file=@plot.png;type=image/png" \
  http://localhost/v1/images
```

```bash
curl http://localhost/v1/images/1 --output downloaded.png
```

```bash
curl -X DELETE -H "X-API-Key: $API_KEY" http://localhost/v1/images/1
```

```bash
curl -X POST -H "X-API-Key: $API_KEY" \
  -H "X-Forwarded-For: 10.0.0.1" \
  -H "Content-Type: application/json" \
  -d '{"source":"demo","payload":{"stid":"123","exnum":"EX1","table":{}}}' \
  http://localhost/v1/events
```

## Development

```bash
python3 -m py_compile app/main.py app/db.py app/models.py app/schemas.py app/security.py
python -m pytest tests/test_security_hardening.py
python test_api.py
docker compose up -d --build
curl http://localhost/health
```
