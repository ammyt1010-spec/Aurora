from fastapi import APIRouter, Depends

from app.core.business_access import require_business_access, require_response_access

from app.api.v1 import (
    analytics,
    auth,
    billing,
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
api_router.include_router(billing.router)
api_router.include_router(projects.router)
api_router.include_router(instruments.router, dependencies=[Depends(require_business_access)])
api_router.include_router(organizations.router)
api_router.include_router(variables.router, dependencies=[Depends(require_business_access)])
api_router.include_router(constructs.router, dependencies=[Depends(require_business_access)])
api_router.include_router(surveys.router, dependencies=[Depends(require_business_access)])
api_router.include_router(studies.router, dependencies=[Depends(require_business_access)])
api_router.include_router(responses.router, dependencies=[Depends(require_response_access)])
api_router.include_router(analytics.router, dependencies=[Depends(require_business_access)])
api_router.include_router(censopas.router, dependencies=[Depends(require_business_access)])
api_router.include_router(exports.router, dependencies=[Depends(require_business_access)])
api_router.include_router(bsc.router, dependencies=[Depends(require_business_access)])
api_router.include_router(reports.router, dependencies=[Depends(require_business_access)])
api_router.include_router(public.router)
api_router.include_router(telemetry.router, dependencies=[Depends(require_business_access)])
api_router.include_router(quick_eval.router)
