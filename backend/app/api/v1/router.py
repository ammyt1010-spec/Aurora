from fastapi import APIRouter

from app.api.v1 import (
    analytics,
    auth,
    bsc,
    censopas,
    constructs,
    exports,
    instruments,
    organizations,
    projects,
    public,
    reports,
    responses,
    studies,
    surveys,
    telemetry,
    variables,
    quick_eval,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(projects.router)
api_router.include_router(instruments.router)
api_router.include_router(organizations.router)
api_router.include_router(variables.router)
api_router.include_router(constructs.router)
api_router.include_router(surveys.router)
api_router.include_router(studies.router)
api_router.include_router(responses.router)
api_router.include_router(analytics.router)
api_router.include_router(censopas.router)
api_router.include_router(exports.router)
api_router.include_router(bsc.router)
api_router.include_router(reports.router)
api_router.include_router(public.router)
api_router.include_router(telemetry.router)
api_router.include_router(quick_eval.router)
