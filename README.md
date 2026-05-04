# DB SQL Service

Small FastAPI service for ingesting JSON events into SQLite and storing uploaded images.

## Configuration

Environment variables:

- `API_KEY`: required value for the `X-API-Key` header on protected endpoints.
- `DATABASE_URL`: SQLAlchemy database URL. Defaults to `sqlite:////data/app.db`.
- `IMAGES_DIR`: directory where uploaded files are stored. Defaults to `/data/images`.
- `MAX_IMAGE_BYTES`: maximum accepted image size in bytes. Defaults to `1048576`.

When running behind Nginx or another reverse proxy, the service uses `X-Forwarded-For` first, then `X-Real-IP`, then the direct client address. Only trust these headers when the app is behind a proxy you control.

## Endpoints

### Events

`POST /v1/events`

- Requires `X-API-Key`.
- Body must include `payload.stid`, `payload.exnum`, and `payload.table`.

`GET /v1/events`

- Requires `X-API-Key`.
- Supports `limit` and `offset`.

`GET /v1/events/{event_id}?exnum=...`

- Requires `X-API-Key`.
- Returns `404` when the id does not exist or the `exnum` does not match.

### Images

`POST /v1/images`

- Requires `X-API-Key`.
- Accepts multipart form field `file`.
- File `Content-Type` must start with `image/`.
- The original filename must include an extension and must not contain path separators.
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

- Requires `X-API-Key`.
- Returns `204` on success and `404` when the image id does not exist.

## Examples

```bash
curl -H "X-API-Key: $API_KEY" \
  -F "file=@plot.png;type=image/png" \
  http://localhost/v1/images
```

```bash
curl http://localhost/v1/images/1 --output downloaded.png
```

```bash
curl -X DELETE -H "X-API-Key: $API_KEY" http://localhost/v1/images/1
```

## Development

```bash
python3 -m py_compile app/main.py app/db.py app/models.py app/schemas.py app/security.py
pytest
docker compose up -d --build
curl http://localhost/health
```
