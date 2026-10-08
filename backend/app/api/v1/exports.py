from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.download_audit import record_file_access
from app.core.security import get_optional_current_user
from app.models.user import User
from app.core.exceptions import NotFoundError
from app.schemas.exports import ExportCreate, ExportRead
from app.services.export_service import ExportService

router = APIRouter(tags=["exports"])

_MEDIA_TYPES = {
    "CSV": "text/csv",
    "XLSX": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "JSON": "application/json",
    "POWERBI": "application/zip",
}


@router.post("/studies/{study_id}/exports", response_model=ExportRead, status_code=201)
async def create_export(
    study_id: int, payload: ExportCreate, session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    service = ExportService(session)
    safe = payload.model_copy(update={"requested_by_user_id": current_user.id}) if current_user else payload
    export = await service.create_export(study_id, safe)
    return ExportRead.model_validate(export)


@router.get("/exports/{export_id}", response_model=ExportRead)
async def get_export(export_id: int, session: AsyncSession = Depends(get_db)):
    service = ExportService(session)
    export = await service.get(export_id)
    return ExportRead.model_validate(export)


@router.get("/studies/{study_id}/exports", response_model=list[ExportRead])
async def list_exports(study_id: int, session: AsyncSession = Depends(get_db)):
    service = ExportService(session)
    exports = await service.list_exports(study_id)
    return [ExportRead.model_validate(export) for export in exports]


@router.get("/exports/{export_id}/download")
async def download_export(export_id: int, session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user)):
    service = ExportService(session)
    export = await service.get(export_id)
    if export.status != "COMPLETED" or not export.storage_path:
        raise NotFoundError(f"Exportación {export_id} no tiene un archivo disponible todavía")

    path = Path(export.storage_path)
    if not path.exists():
        raise NotFoundError(f"Archivo de exportación {export_id} no encontrado en almacenamiento")

    await record_file_access(session, action="EXPORT_DOWNLOADED", entity_type="export",
        entity_id=export_id, study_id=export.study_id,
        user_id=current_user.id if current_user else None)
    return FileResponse(
        path=path,
        media_type=_MEDIA_TYPES.get(export.export_type, "application/octet-stream"),
        filename=path.name,
    )
