from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import ReportRun, ReportTemplate


class ReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_template(self, template: ReportTemplate) -> ReportTemplate:
        self.session.add(template)
        await self.session.flush()
        return template

    async def get_template(self, template_id: int) -> ReportTemplate | None:
        return await self.session.get(ReportTemplate, template_id)

    async def list_templates(self, discipline: str | None = None) -> list[ReportTemplate]:
        from sqlalchemy import select
        stmt = select(ReportTemplate).where(ReportTemplate.status != "ARCHIVED").order_by(ReportTemplate.id.asc())
        templates = list((await self.session.execute(stmt)).scalars().all())
        if discipline:
            disc_clean = discipline.strip().upper()
            filtered = []
            for t in templates:
                cfg = t.template_config or {}
                t_disc = str(cfg.get("discipline") or t.report_type or "").upper()
                if disc_clean in t_disc or t_disc in disc_clean:
                    filtered.append(t)
            return filtered
        return templates

    async def add_run(self, run: ReportRun) -> ReportRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_run(self, run_id: int) -> ReportRun | None:
        return await self.session.get(ReportRun, run_id)

