# app/main.py
from pathlib import Path
from contextlib import asynccontextmanager
import logging
import os
import uuid

from fastapi import Depends, File, FastAPI, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .db import Base, SessionLocal, engine
from .models import Event, Image
from .schemas import EventIn, EventOut
from .security import is_demo_mode_enabled, require_allowed_ip, require_api_key

logger = logging.getLogger(__name__)

# Create tables (simple approach; for production consider migrations)
Base.metadata.create_all(bind=engine)

# Setup image storage directory
IMAGES_DIR = Path(os.getenv("IMAGES_DIR", "/data/images"))
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
MAX_IMAGE_BYTES = int(os.getenv("MAX_IMAGE_BYTES", str(1024 * 1024)))


@asynccontextmanager
async def lifespan(app: FastAPI):
    if is_demo_mode_enabled():
        logger.warning("DEMO_MODE is enabled: image upload/delete IP allowlist checks are bypassed")
    yield


app = FastAPI(
    title="SQLite Ingestion Service",
    version="1.0.0",
    docs_url=None,        # disable Swagger UI in production
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}


# ----------------------------
# CREATE (POST) - store payload
# ----------------------------
@app.post("/v1/events", response_model=EventOut, dependencies=[Depends(require_api_key)])
def create_event(body: EventIn, db: Session = Depends(get_db)):
    """
    Expected body:
    {
      "source": "optional-string",
      "payload": {
        "stid": "...",
        "exnum": "...",
        "table": {...}
      }
    }
    """
    if not isinstance(body.payload, dict):
        raise HTTPException(status_code=400, detail="payload must be a JSON object")

    # Optional: enforce required keys inside payload
    for key in ("stid", "exnum", "table"):
        if key not in body.payload:
            raise HTTPException(status_code=422, detail=f"payload must include '{key}'")

    e = Event(source=body.source, payload=body.payload)
    db.add(e)
    db.commit()
    db.refresh(e)

    return EventOut(
        id=e.id,
        received_at=e.received_at.isoformat(),
        source=e.source,
        payload=e.payload,
    )


# ----------------------------
# READ - list events (paginated)
# ----------------------------
@app.get("/v1/events", response_model=list[EventOut], dependencies=[Depends(require_api_key)])
def list_events(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    rows = (
        db.query(Event)
        .order_by(desc(Event.id))
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        EventOut(
            id=e.id,
            received_at=e.received_at.isoformat(),
            source=e.source,
            payload=e.payload,
        )
        for e in rows
    ]


# ---------------------------------------------------------
# READ - get event by stid (user ID) and exnum
# ---------------------------------------------------------
@app.get("/v1/events/{event_id}", response_model=EventOut, dependencies=[Depends(require_api_key)])
def get_event_by_id_and_exnum(
    event_id: str,
    exnum: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    """
    Call example:
      GET /v1/events/student123?exnum=EX1

    Returns the most recent event matching both stid and exnum.
    Returns 404 if no matching event exists.
    """
    events = (
        db.query(Event)
        .order_by(desc(Event.id))
        .all()
    )

    for e in events:
        p = e.payload or {}
        if isinstance(p, dict) and p.get("stid") == event_id and p.get("exnum") == exnum:
            return EventOut(
                id=e.id,
                received_at=e.received_at.isoformat(),
                source=e.source,
                payload=e.payload,
            )

    raise HTTPException(status_code=404, detail="Not found")


# ----------------------------
# IMAGE ENDPOINTS
# ----------------------------
@app.post(
    "/v1/images",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key), Depends(require_allowed_ip)],
)
def upload_image(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload an image file.

    Returns: {"id": 1, "image_id": 1, "image_url": "https://your-host/images/random-name.png"}
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image (e.g., jpg, png, gif, webp)")

    original_filename = file.filename or ""
    if "/" in original_filename or "\\" in original_filename or original_filename.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_ext = Path(original_filename).suffix.lower()
    if not file_ext:
        raise HTTPException(status_code=400, detail="Image filename must include an extension")

    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = IMAGES_DIR / unique_filename

    total_size = 0
    try:
        with open(file_path, "wb") as buffer:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > MAX_IMAGE_BYTES:
                    raise HTTPException(status_code=413, detail=f"Image exceeds {MAX_IMAGE_BYTES} byte limit")
                buffer.write(chunk)
    except Exception as e:
        if file_path.exists():
            file_path.unlink()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Failed to save image: {str(e)}")
    finally:
        file.file.close()

    image = Image(
        filename=unique_filename,
        content_type=file.content_type,
        size=total_size,
        storage_path=str(file_path),
    )
    db.add(image)
    try:
        db.commit()
        db.refresh(image)
    except Exception as e:
        db.rollback()
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Failed to save image metadata: {str(e)}")

    return {
        "id": image.id,
        "image_id": image.id,
        "image_url": str(request.url_for("images", path=image.filename)),
    }


@app.get("/v1/images/{image_id}")
def get_image(image_id: int, db: Session = Depends(get_db)):
    """
    Retrieve an image by id. This endpoint is intentionally public.
    """
    image = db.get(Image, image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    file_path = Path(image.storage_path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(file_path, media_type=image.content_type)


@app.delete("/v1/images/{image_id}", dependencies=[Depends(require_api_key), Depends(require_allowed_ip)])
def delete_image(image_id: int, db: Session = Depends(get_db)):
    """
    Delete an image by id.

    Returns: 204 No Content on success, 404 if not found.
    """
    image = db.get(Image, image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    file_path = Path(image.storage_path)
    try:
        if file_path.exists():
            file_path.unlink()
        db.delete(image)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete image: {str(e)}")

    return Response(status_code=204)
