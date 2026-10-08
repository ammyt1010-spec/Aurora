"""Exportaciones (harness §37).

Se ejecuta síncronamente (datasets pequeños en esta fase; §37 sugiere
streaming/archivos temporales para datasets grandes, fuera de alcance aquí).

Implementado: CSV, XLSX, JSON. `SPSS` (pyreadstat), `POWERBI`/`PARQUET`
quedan pendientes — requieren dependencias adicionales (pyreadstat, polars)
que no se instalan todavía; se documenta explícitamente en vez de fallar
silenciosamente.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from openpyxl import Workbook
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationDomainError
from app.models.export import Export
from app.repositories.exports import ExportRepository
from app.repositories.studies import StudyRepository
from app.schemas.exports import ExportCreate
from app.schemas.datasets import LongDatasetRow
from app.services.dataset_service import DatasetService

_UNIMPLEMENTED_TYPES = {
    "SPSS": "requiere pyreadstat",
    "PARQUET": "requiere polars/pyarrow",
}


def spreadsheet_safe(value):
    """Neutralize spreadsheet formulas without changing JSON/raw database values."""
    if not isinstance(value, str):
        return value
    candidate = value.lstrip(" \\t\\r\\n")
    if candidate and candidate[0] in ("=", "+", "-", "@"):
        return "'" + value
    return value


def spreadsheet_rows(rows: list[dict], columns: list[str]) -> list[dict]:
    return [
        {column: spreadsheet_safe(row.get(column)) for column in columns}
        for row in rows
    ]


class ExportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ExportRepository(session)
        self.study_repo = StudyRepository(session)
        self.dataset_service = DatasetService(session)

    async def get(self, export_id: int) -> Export:
        export = await self.repo.get(export_id)
        if export is None:
            raise NotFoundError(f"Exportación {export_id} no encontrada")
        return export

    async def list_exports(self, study_id: int) -> list[Export]:
        """Trazabilidad de exportaciones (harness §73): historial por estudio."""
        study = await self.study_repo.get(study_id)
        if study is None:
            raise NotFoundError(f"Estudio {study_id} no encontrado")
        return await self.repo.list_by_study(study_id)

    async def create_export(self, study_id: int, payload: ExportCreate) -> Export:
        study = await self.study_repo.get(study_id)
        if study is None:
            raise NotFoundError(f"Estudio {study_id} no encontrado")

        export = Export(
            study_id=study_id,
            export_type=payload.export_type,
            dataset_shape=payload.dataset_shape,
            requested_by_user_id=payload.requested_by_user_id,
            filters=payload.filters,
            status="PENDING",
        )
        export = await self.repo.create(export)
        await self.session.flush()

        try:
            rows, columns = await self._load_rows(study_id, payload.dataset_shape)
            if payload.filters:
                rows = DatasetService.apply_filters(rows, payload.filters)
            if len(rows) > get_settings().max_export_rows:
                raise ValidationDomainError("La exportación supera el límite de filas configurado. Filtra o divide el dataset.")
            path = self._write_file(str(export.public_id), payload.export_type, rows, columns)

            export.storage_path = str(path)
            export.row_count = len(rows)
            export.status = "COMPLETED"
            export.generated_at = datetime.now(UTC)
        except Exception as exc:
            export.status = "FAILED"
            export.error_message = str(exc)
            await self.session.commit()
            raise

        await self.session.commit()
        await self.session.refresh(export)
        return export

    async def _load_rows(self, study_id: int, shape: str) -> tuple[list[dict], list[str]]:
        if shape == "LONG":
            data = await self.dataset_service.load_long_dataset(study_id)
            rows = [row.model_dump() for row in data.rows]
            columns = list(LongDatasetRow.model_fields.keys())
            return rows, columns

        if shape == "WIDE":
            data = await self.dataset_service.load_wide_dataset(study_id)
            return data.rows, data.columns

        raise ValidationDomainError(
            "La forma AGGREGATED todavía no está implementada; use LONG o WIDE."
        )

    def _write_file(self, public_id: str, export_type: str, rows: list[dict], columns: list[str]) -> Path:
        if export_type in _UNIMPLEMENTED_TYPES:
            raise ValidationDomainError(
                f"Exportación '{export_type}' no implementada en esta fase "
                f"({_UNIMPLEMENTED_TYPES[export_type]}).",
                export_type=export_type,
            )

        storage_dir = Path(get_settings().export_storage_dir)
        storage_dir.mkdir(parents=True, exist_ok=True)

        if export_type == "CSV":
            path = storage_dir / f"{public_id}.csv"
            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=columns)
                writer.writeheader()
                writer.writerows(spreadsheet_rows(rows, columns))
            return path

        if export_type == "XLSX":
            path = storage_dir / f"{public_id}.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.append(columns)
            for row in rows:
                sheet.append([spreadsheet_safe(row.get(column)) for column in columns])
            workbook.save(path)
            return path

        if export_type == "POWERBI":
            # Portable import bundle, not a proprietary .pbix report.
            path = storage_dir / f"{public_id}.zip"
            stream = io.StringIO(newline="")
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows(spreadsheet_rows(rows, columns))
            dictionary = {
                "format": "AURORA_POWERBI_CSV_IMPORT_V1",
                "rows": len(rows),
                "columns": [{"name": name} for name in columns],
                "encoding": "UTF-8",
                "delimiter": ",",
                "contains_identifiers": False,
            }
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
                bundle.writestr("dataset.csv", stream.getvalue().encode("utf-8-sig"))
                bundle.writestr("data_dictionary.json", json.dumps(dictionary, ensure_ascii=False, indent=2))
                bundle.writestr(
                    "LEEME.txt",
                    "AURORA Professional - Paquete de importación Power BI\\n"
                    "Este ZIP no es un archivo PBIX. En Power BI Desktop selecciona "
                    "Obtener datos > Texto/CSV e importa dataset.csv como UTF-8.\\n"
                    "Los valores de texto con prefijos de fórmula se neutralizan "
                    "para evitar ejecución al abrirlos en hojas de cálculo.\\n",
                )
            return path

        if export_type == "JSON":
            path = storage_dir / f"{public_id}.json"
            path.write_text(
                json.dumps(rows, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
            )
            return path

        raise ValidationDomainError(f"Tipo de exportación '{export_type}' desconocido.")
