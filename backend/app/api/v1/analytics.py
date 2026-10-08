from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user, get_optional_current_user
from app.models.analytics_plan import AnalyticsPlan, AnalyticsPlanTool
from app.models.study import Study
from app.models.project import Project
from app.models.user import User
from app.schemas.analytics import (
    AnalysisMethodRead,
    AnalysisRunCreate,
    AnalysisRunRead,
    AvailableMethodsRequest,
    AvailableMethodsResponse,
    CompareGroupsRequest,
    ConstructCompareGroupsRequest,
    ConstructCompareGroupsResponse,
    CorrelationRequest,
    CrosstabRequest,
    DescribeRequest,
    FrequenciesRequest,
    KMeansRequest,
    LogisticRegressionRequest,
    NormalityRequest,
    NormalityResponse,
    ReliabilityRequest,
    SpearmanMatrixRequest,
    SpearmanMatrixResponse,
)
from app.schemas.censopas import StudyAnalyticsToolsResponse, AnalyticsToolCatalogRead
from app.services.analysis_service import AnalysisService
from app.services.advanced_analysis_service import AdvancedAnalysisService
from app.services.project_service import ProjectService

router = APIRouter(tags=["analytics"])


@router.get("/analytics/methods", response_model=list[AnalysisMethodRead])
async def list_analysis_methods(session: AsyncSession = Depends(get_db)):
    service = AnalysisService(session)
    methods = await service.list_methods()
    return [AnalysisMethodRead.model_validate(m) for m in methods]


@router.get("/studies/{study_id}/analytics/tools", response_model=StudyAnalyticsToolsResponse)
async def study_analytics_tools(
    study_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    study = (
        await session.execute(
            select(Study).where(Study.id == study_id).options(
                selectinload(Study.analytics_plan)
                .selectinload(AnalyticsPlan.tools)
                .selectinload(AnalyticsPlanTool.tool)
            )
        )
    ).scalar_one_or_none()
    if study is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Estudio {study_id} no encontrado")
    project = await session.get(Project, study.project_id)
    if project is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Proyecto del estudio {study_id} no encontrado")
    await ProjectService(session).ensure_access(project, current_user, write=False)
    plan = study.analytics_plan
    if plan is None:
        return StudyAnalyticsToolsResponse(study_id=study_id, plan_code="STANDARD", plan_name="Estándar")
    return StudyAnalyticsToolsResponse(
        study_id=study_id,
        plan_code=plan.code,
        plan_name=plan.name,
        tools=[
            AnalyticsToolCatalogRead(
                code=link.tool.code,
                name=link.tool.name,
                category=link.tool.category,
                description=link.tool.description,
            )
            for link in plan.tools
            if link.enabled and link.tool.is_active
        ],
    )


@router.post(
    "/studies/{study_id}/analytics/available-methods", response_model=AvailableMethodsResponse
)
async def available_methods(
    study_id: int, payload: AvailableMethodsRequest, session: AsyncSession = Depends(get_db)
):
    del study_id
    service = AnalysisService(session)
    methods = await service.available_methods(payload.variable_ids)
    return AvailableMethodsResponse(methods=methods)


@router.post("/studies/{study_id}/analytics/describe", response_model=AnalysisRunRead)
async def describe(
    study_id: int, payload: DescribeRequest, session: AsyncSession = Depends(get_db)
):
    service = AnalysisService(session)
    run = await service.run_descriptive(study_id, payload)
    return AnalysisRunRead.model_validate(run)


@router.post("/studies/{study_id}/analytics/frequencies", response_model=AnalysisRunRead)
async def frequencies(
    study_id: int, payload: FrequenciesRequest, session: AsyncSession = Depends(get_db)
):
    service = AnalysisService(session)
    run = await service.run_frequencies(study_id, payload)
    return AnalysisRunRead.model_validate(run)


@router.post("/studies/{study_id}/analytics/crosstab", response_model=AnalysisRunRead)
async def crosstab(
    study_id: int, payload: CrosstabRequest, session: AsyncSession = Depends(get_db)
):
    service = AnalysisService(session)
    run = await service.run_crosstab(study_id, payload)
    return AnalysisRunRead.model_validate(run)


@router.post("/studies/{study_id}/analytics/compare-groups", response_model=AnalysisRunRead)
async def compare_groups(
    study_id: int, payload: CompareGroupsRequest, session: AsyncSession = Depends(get_db)
):
    service = AnalysisService(session)
    run = await service.run_compare_groups(study_id, payload)
    return AnalysisRunRead.model_validate(run)


@router.post("/studies/{study_id}/analytics/correlation", response_model=AnalysisRunRead)
async def correlation(
    study_id: int, payload: CorrelationRequest, session: AsyncSession = Depends(get_db)
):
    service = AnalysisService(session)
    run = await service.run_correlation(study_id, payload)
    return AnalysisRunRead.model_validate(run)


@router.post("/studies/{study_id}/analytics/reliability", response_model=AnalysisRunRead)
async def reliability(
    study_id: int, payload: ReliabilityRequest, session: AsyncSession = Depends(get_db)
):
    service = AnalysisService(session)
    run = await service.run_reliability(study_id, payload)
    return AnalysisRunRead.model_validate(run)


@router.post("/studies/{study_id}/analytics/logistic-regression", response_model=AnalysisRunRead)
async def logistic_regression(
    study_id: int, payload: LogisticRegressionRequest, session: AsyncSession = Depends(get_db)
):
    service = AnalysisService(session)
    run = await service.run_logistic_regression(study_id, payload)
    return AnalysisRunRead.model_validate(run)


@router.post("/studies/{study_id}/analytics/kmeans", response_model=AnalysisRunRead)
async def kmeans(study_id: int, payload: KMeansRequest, session: AsyncSession = Depends(get_db)):
    service = AnalysisService(session)
    run = await service.run_kmeans(study_id, payload)
    return AnalysisRunRead.model_validate(run)


@router.post(
    "/studies/{study_id}/analytics/normality", response_model=NormalityResponse
)
async def normality(
    study_id: int, payload: NormalityRequest, session: AsyncSession = Depends(get_db)
):
    return await AdvancedAnalysisService(session).run_normality(study_id, payload)


@router.post(
    "/studies/{study_id}/analytics/spearman-matrix",
    response_model=SpearmanMatrixResponse,
)
async def spearman_matrix(
    study_id: int,
    payload: SpearmanMatrixRequest,
    current_user: User | None = Depends(get_optional_current_user),
    session: AsyncSession = Depends(get_db),
):
    await AnalysisService(session).require_plan_tools(study_id, ["SPEARMAN"])
    return await AdvancedAnalysisService(session).run_spearman_matrix(
        study_id, payload, current_user
    )


@router.post(
    "/studies/{study_id}/analytics/construct-compare-groups",
    response_model=ConstructCompareGroupsResponse,
)
async def construct_compare_groups(
    study_id: int,
    payload: ConstructCompareGroupsRequest,
    session: AsyncSession = Depends(get_db),
):
    await AnalysisService(session).require_plan_tools(study_id, ["MANN_WHITNEY", "KRUSKAL_WALLIS"])
    return await AdvancedAnalysisService(session).compare_construct_groups(study_id, payload)


@router.post("/studies/{study_id}/analysis-runs", response_model=AnalysisRunRead, status_code=201)
async def create_analysis_run(
    study_id: int, payload: AnalysisRunCreate, session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    service = AnalysisService(session)
    safe = payload.model_copy(update={"requested_by_user_id": current_user.id}) if current_user else payload
    run = await service.run_generic(study_id, safe)
    return AnalysisRunRead.model_validate(run)


@router.get("/analysis-runs/{run_id}", response_model=AnalysisRunRead)
async def get_analysis_run(run_id: int, session: AsyncSession = Depends(get_db)):
    service = AnalysisService(session)
    run = await service.get_run(run_id)
    return AnalysisRunRead.model_validate(run)
