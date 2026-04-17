from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import re
import uuid

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.config import Settings
from app.job_manager import JobManager, JobNotFoundError, JobStateError
from app.model_manager import ModelManagerError, ModelNotFoundError, ModelStateError
from app.pdf_export import render_markdown_pdf
from app.preview import markdown_to_safe_html
from app.types import JobStatus


FILENAME_SAFE_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


class RetryRequest(BaseModel):
    include_timestamps: bool | None = None


class InstallModelRequest(BaseModel):
    model_id: str


class SelectModelRequest(BaseModel):
    model_id: str


class DocumentUpdateRequest(BaseModel):
    markdown: str


class DesktopSettingsUpdateRequest(BaseModel):
    cleanup_uploads_on_close: bool
    cleanup_queue_on_close: bool


def sanitize_filename(filename: str) -> str:
    cleaned = FILENAME_SAFE_PATTERN.sub("_", filename.strip())
    return cleaned or "audio"


async def save_upload_to_path(upload: UploadFile, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as out:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    await upload.close()


def create_app(settings: Settings | None = None, job_manager: JobManager | None = None) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    resolved_settings.ensure_directories()
    manager = job_manager or JobManager(resolved_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await manager.start()
        try:
            yield
        finally:
            await manager.shutdown()

    app = FastAPI(title="Voctarium STT", version="0.2.0", lifespan=lifespan)
    templates = Jinja2Templates(directory=str(resolved_settings.resource_root / "app" / "templates"))
    app.mount(
        "/static",
        StaticFiles(directory=str(resolved_settings.resource_root / "app" / "static")),
        name="static",
    )

    app.state.settings = resolved_settings
    app.state.job_manager = manager

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "default_model": app.state.job_manager.model_manager.active_model_id() or "",
            },
        )

    @app.get("/jobs/{job_id}", response_class=HTMLResponse)
    async def job_result_page(request: Request, job_id: str) -> HTMLResponse:
        payload = app.state.job_manager.get_job_payload(job_id)
        job_exists = payload is not None
        return templates.TemplateResponse(
            request,
            "job_result.html",
            {
                "job_id": job_id,
                "job_exists": job_exists,
            },
            status_code=200 if job_exists else 404,
        )

    @app.get("/health")
    async def health() -> dict:
        return app.state.job_manager.health_payload()

    @app.post("/api/jobs")
    async def create_job(
        file: UploadFile = File(...),
        model_id: str | None = Form(default=None),
        include_timestamps: bool = Form(False),
    ) -> dict:
        original_filename = file.filename or "audio"
        safe_name = sanitize_filename(original_filename)
        destination = resolved_settings.uploads_dir / f"{uuid.uuid4().hex}_{safe_name}"
        await save_upload_to_path(file, destination)

        if destination.stat().st_size == 0:
            destination.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        try:
            job, queue_position = app.state.job_manager.create_job(
                input_path=destination,
                original_filename=original_filename,
                model_id=model_id,
                include_timestamps=include_timestamps,
            )
        except ModelNotFoundError as exc:
            destination.unlink(missing_ok=True)
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (JobStateError, ModelManagerError) as exc:
            destination.unlink(missing_ok=True)
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "job_id": job.job_id,
            "status": job.status.value,
            "queue_position": queue_position,
        }

    @app.get("/api/jobs")
    async def list_jobs(limit: int = Query(default=100, ge=1, le=500)) -> dict:
        items, total = app.state.job_manager.list_job_payloads(limit=limit)
        return {"items": items, "total": total}

    @app.get("/api/jobs/{job_id}")
    async def get_job(job_id: str) -> dict:
        payload = app.state.job_manager.get_job_payload(job_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        return payload

    @app.post("/api/jobs/{job_id}/retry")
    async def retry_job(job_id: str, request: RetryRequest) -> dict:
        try:
            new_job, queue_position = app.state.job_manager.retry_job(
                job_id=job_id,
                include_timestamps_override=request.include_timestamps,
            )
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except JobStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        return {
            "job_id": new_job.job_id,
            "status": new_job.status.value,
            "queue_position": queue_position,
            "retry_of_job_id": job_id,
        }

    @app.get("/api/models/faster-whisper")
    async def list_faster_whisper_models() -> dict:
        manager = app.state.job_manager.model_manager
        return {
            "active_model_id": manager.active_model_id(),
            "items": manager.list_models(),
        }

    @app.get("/api/settings/desktop")
    async def get_desktop_settings() -> dict:
        return app.state.job_manager.model_manager.desktop_settings()

    @app.put("/api/settings/desktop")
    async def update_desktop_settings(request: DesktopSettingsUpdateRequest) -> dict:
        return app.state.job_manager.model_manager.update_desktop_settings(
            cleanup_uploads_on_close=request.cleanup_uploads_on_close,
            cleanup_queue_on_close=request.cleanup_queue_on_close,
        )

    @app.post("/api/models/faster-whisper/install")
    async def install_faster_whisper_model(request: InstallModelRequest) -> dict:
        manager = app.state.job_manager.model_manager
        try:
            return manager.install_model(request.model_id)
        except ModelNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ModelStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/models/faster-whisper/select")
    async def select_faster_whisper_model(request: SelectModelRequest) -> dict:
        manager = app.state.job_manager.model_manager
        try:
            return manager.select_model(request.model_id)
        except ModelNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ModelStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.delete("/api/models/faster-whisper/{model_id}")
    async def delete_faster_whisper_model(model_id: str) -> dict:
        manager = app.state.job_manager.model_manager
        try:
            if app.state.job_manager.is_model_locked(model_id):
                raise ModelStateError("Model is still used by queued or processing jobs.")
            return manager.delete_model(model_id)
        except ModelNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ModelStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.delete("/api/jobs/{job_id}")
    async def delete_job(job_id: str) -> dict:
        try:
            deleted = app.state.job_manager.delete_job(job_id)
        except JobStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        if not deleted:
            raise HTTPException(status_code=404, detail="Job not found.")
        return {"deleted": True}

    @app.post("/api/jobs/{job_id}/cancel")
    async def cancel_job(job_id: str) -> dict:
        try:
            app.state.job_manager.cancel_job(job_id)
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except JobStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        payload = app.state.job_manager.get_job_payload(job_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        return payload

    def resolve_readable_result(job_id: str) -> tuple[dict, Path]:
        try:
            return app.state.job_manager.get_effective_document_path(job_id, "readable")
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except JobStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Result is unavailable.") from exc

    @app.get("/api/jobs/{job_id}/documents/readable")
    async def get_document(job_id: str) -> dict:
        try:
            return app.state.job_manager.get_document_payload(job_id, "readable")
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except JobStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.put("/api/jobs/{job_id}/documents/readable")
    async def update_document(job_id: str, request: DocumentUpdateRequest) -> dict:
        try:
            return app.state.job_manager.save_document_override(job_id, "readable", request.markdown)
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except JobStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.delete("/api/jobs/{job_id}/documents/readable")
    async def reset_document(job_id: str) -> dict:
        try:
            return app.state.job_manager.reset_document_override(job_id, "readable")
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except JobStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/jobs/{job_id}/readable.md")
    async def get_job_readable_result(job_id: str) -> FileResponse:
        _, path = resolve_readable_result(job_id)
        return FileResponse(
            path=path,
            media_type="text/markdown; charset=utf-8",
            filename=f"{job_id}.readable.md",
        )

    @app.get("/api/jobs/{job_id}/readable.preview", response_class=HTMLResponse)
    async def get_job_readable_preview(job_id: str) -> HTMLResponse:
        _, path = resolve_readable_result(job_id)
        markdown_text = path.read_text(encoding="utf-8")
        html_content = markdown_to_safe_html(markdown_text)
        return HTMLResponse(content=html_content)

    @app.get("/api/jobs/{job_id}/readable.pdf")
    async def get_job_readable_pdf(
        job_id: str,
        font_size_px: int = Query(default=18, ge=12, le=32),
        line_height_mode: str = Query(default="normal"),
        align_mode: str = Query(default="justify"),
        paragraph_gap: bool = Query(default=False),
        content_width_percent: int = Query(default=100, ge=50, le=100),
    ) -> Response:
        payload, path = resolve_readable_result(job_id)
        pdf_bytes = render_markdown_pdf(
            path.read_text(encoding="utf-8"),
            fallback_title=payload.get("original_filename"),
            font_size_px=font_size_px,
            line_height_mode=line_height_mode,
            align_mode=align_mode,
            paragraph_gap=paragraph_gap,
            content_width_percent=content_width_percent,
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{job_id}.readable.pdf"'},
        )

    return app


app = create_app()
