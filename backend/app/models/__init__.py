"""Registro central de modelos ORM (Fase 1+2).

Importar este módulo garantiza que todas las clases queden registradas en
`Base.metadata`, necesario tanto para Alembic autogenerate como para
`Base.metadata.create_all()` en tests con SQLite.
"""

from app.models.analysis import AnalysisMethod, AnalysisResult, AnalysisRun
from app.models.analytics_plan import (
    AnalyticsPlan,
    AnalyticsPlanTool,
    OrganizationCollaboratorCode,
    StatisticalTool,
)
from app.models.audit import AuditLog
from app.models.billing import ReportTariff, ReportOrder
from app.models.base import Base
from app.models.censopas import Barem, BaremBand, BaremCutoff, ConstructResult, ConstructScore, ResponseScore
from app.models.bsc import ActionPlan, ActionPlanItem, Kpi, KpiMeasurement
from app.models.export import Export
from app.models.report import ReportRun, ReportTemplate
from app.models.construct import Construct, ConstructItem
from app.models.instrument import Instrument, InstrumentVersion
from app.models.option_set import OptionSet, OptionSetOption
from app.models.participant import Participant, StudyInvitation
from app.models.project import Project, ProjectMember
from app.models.question import Question
from app.models.response import Response, ResponseSelectedOption, ResponseSession, ResponseSessionUnit
from app.models.scoring import ScoringRule
from app.models.study import Study, StudySnapshot, StudyUnit, StudyUnitType
from app.models.survey import Survey, SurveyQuestion, SurveySection
from app.models.user import Organization, OrganizationMembership, User
from app.models.variable import Variable

__all__ = [
    "Base",
    "User",
    "Organization",
    "OrganizationMembership",
    "Project",
    "ProjectMember",
    "Instrument",
    "InstrumentVersion",
    "OptionSet",
    "OptionSetOption",
    "Question",
    "Construct",
    "ConstructItem",
    "ScoringRule",
    "Variable",
    "AuditLog",
    "ReportTariff",
    "ReportOrder",
    "Survey",
    "SurveySection",
    "SurveyQuestion",
    "Study",
    "StudySnapshot",
    "StudyUnitType",
    "StudyUnit",
    "ResponseSession",
    "ResponseSessionUnit",
    "Response",
    "ResponseSelectedOption",
    "AnalysisMethod",
    "AnalysisRun",
    "AnalysisResult",
    "AnalyticsPlan",
    "StatisticalTool",
    "AnalyticsPlanTool",
    "OrganizationCollaboratorCode",
    "ResponseScore",
    "Barem",
    "BaremBand",
    "BaremCutoff",
    "ConstructResult",
    "ConstructScore",
    "Export",
    "ActionPlan",
    "ActionPlanItem",
    "Kpi",
    "KpiMeasurement",
    "ReportTemplate",
    "ReportRun",
    "Participant",
    "StudyInvitation",
]
