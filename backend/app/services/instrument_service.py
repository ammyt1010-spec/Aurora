from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.core.pagination import Page, PageParams, paginate
from app.models.construct import Construct, ConstructItem
from app.models.instrument import Instrument, InstrumentVersion
from app.models.option_set import OptionSet, OptionSetOption
from app.models.project import Project
from app.models.question import Question
from app.models.scoring import ScoringRule
from app.models.variable import Variable
from app.repositories.instruments import InstrumentRepository
from app.schemas.instruments import (
    ConstructMatrix,
    ConstructMatrixRow,
    InstrumentCreate,
    InstrumentRead,
    InstrumentTree,
    InstrumentTreeConstruct,
    InstrumentTreeVariable,
    InstrumentTreeItem,
    InstrumentVersionCloneRequest,
    InstrumentVersionCreate,
    InstrumentVersionUpdate,
)
from app.services.audit_service import AuditService
from app.services.instrument_edit_policy import InstrumentEditPolicy


class InstrumentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = InstrumentRepository(session)
        self.audit = AuditService(session)

    # --- Instruments -------------------------------------------------------

    async def create(
        self, payload: InstrumentCreate, *, project_id: int | None = None
    ) -> Instrument:
        resolved_project_id = project_id if project_id is not None else payload.project_id
        if resolved_project_id is not None:
            project = await self.session.get(Project, resolved_project_id)
            if project is None:
                raise NotFoundError(f"Proyecto {resolved_project_id} no encontrado")
        instrument = Instrument(
            project_id=resolved_project_id,
            owner_user_id=payload.owner_user_id,
            organization_id=payload.organization_id,
            code=payload.code,
            name=payload.name,
            instrument_type=payload.instrument_type,
            description=payload.description,
            source_name=payload.source_name,
            source_url=payload.source_url,
            is_system=payload.is_system,
            metadata_=payload.metadata,
        )
        instrument = await self.repo.create(instrument)
        await self.audit.log(
            action="INSTRUMENT_CREATED", entity_type="instrument", entity_id=instrument.id
        )
        await self.session.commit()
        return instrument

    async def get(self, instrument_id: int) -> Instrument:
        instrument = await self.repo.get(instrument_id)
        if instrument is None:
            raise NotFoundError(f"Instrumento {instrument_id} no encontrado")
        return instrument

    async def list(
        self, params: PageParams, *, project_id: int | None = None, owner_user_id: int | None = None
    ) -> Page[InstrumentRead]:
        if project_id is not None and await self.session.get(Project, project_id) is None:
            raise NotFoundError(f"Proyecto {project_id} no encontrado")
        stmt = self.repo.list_stmt(project_id=project_id)
        if project_id is None and owner_user_id is not None:
            stmt = stmt.where(or_(Instrument.is_system.is_(True), Instrument.owner_user_id == owner_user_id))
        items, total = await paginate(self.session, stmt, params)
        return Page[InstrumentRead](
            items=[InstrumentRead.model_validate(item) for item in items],
            page=params.page,
            page_size=params.page_size,
            total=total,
        )

    # --- Versions ------------------------------------------------------------

    async def create_version(
        self, instrument_id: int, payload: InstrumentVersionCreate
    ) -> InstrumentVersion:
        await self.get(instrument_id)
        version = InstrumentVersion(
            instrument_id=instrument_id,
            version_code=payload.version_code,
            version_name=payload.version_name,
            edition=payload.edition,
            valid_from=payload.valid_from,
            valid_to=payload.valid_to,
            status=payload.status,
            source_reference=payload.source_reference,
            config=payload.config,
        )
        version = await self.repo.create_version(version)
        await self.audit.log(
            action="INSTRUMENT_VERSION_CREATED",
            entity_type="instrument_version",
            entity_id=version.id,
        )
        await self.session.commit()
        return version

    async def get_version(self, version_id: int) -> InstrumentVersion:
        version = await self.repo.get_version_with_instrument(version_id)
        if version is None:
            raise NotFoundError(f"Versión de instrumento {version_id} no encontrada")
        return version

    async def list_versions(self, instrument_id: int) -> list[InstrumentVersion]:
        await self.get(instrument_id)
        return await self.repo.list_versions(instrument_id)

    async def update_version(
        self, version_id: int, payload: InstrumentVersionUpdate
    ) -> InstrumentVersion:
        version = await self.get_version(version_id)
        await InstrumentEditPolicy.can_edit_version(self.session, version.instrument, version)

        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(version, field, value)

        await self.session.flush()
        await self.audit.log(
            action="INSTRUMENT_VERSION_UPDATED",
            entity_type="instrument_version",
            entity_id=version.id,
            after_data=data,
        )
        await self.session.commit()
        await self.session.refresh(version)
        return version

    # --- Clonar / versionar (harness §13) -------------------------------------

    async def clone_version(
        self, instrument_id: int, version_id: int, payload: InstrumentVersionCloneRequest
    ) -> InstrumentVersion:
        """Clona una versión completa generando IDs nuevos.

        Siempre permitido, incluso si la versión origen está bloqueada — es
        precisamente el mecanismo para editar un instrumento protegido sin
        destruir la versión anterior (§13, §56). Transaccional (§49): si algo
        falla a mitad de copia, se hace rollback completo.
        """
        source = await self.get_version(version_id)
        if source.instrument_id != instrument_id:
            raise NotFoundError("La versión no pertenece a este instrumento")

        try:
            new_version = InstrumentVersion(
                instrument_id=instrument_id,
                version_code=payload.version_code,
                version_name=payload.version_name or f"{source.version_name} (copia)",
                edition=source.edition,
                status="DRAFT",
                scoring_status="NOT_CONFIGURED",
                source_reference=source.source_reference,
                config=dict(source.config),
            )
            self.session.add(new_version)
            await self.session.flush()

            # 1) option_sets + options
            option_set_id_map: dict[int, int] = {}
            option_id_map: dict[int, int] = {}
            option_sets_stmt = select(OptionSet).where(
                OptionSet.instrument_version_id == version_id
            ).options(selectinload(OptionSet.options))
            source_option_sets = (await self.session.execute(option_sets_stmt)).scalars().all()
            for src_os in source_option_sets:
                new_os = OptionSet(
                    instrument_version_id=new_version.id,
                    owner_user_id=src_os.owner_user_id,
                    code=src_os.code,
                    name=src_os.name,
                    description=src_os.description,
                    metadata_=dict(src_os.metadata_),
                )
                self.session.add(new_os)
                await self.session.flush()
                option_set_id_map[src_os.id] = new_os.id

                for src_opt in src_os.options:
                    new_opt = OptionSetOption(
                        option_set_id=new_os.id,
                        raw_code=src_opt.raw_code,
                        label=src_opt.label,
                        numeric_value=src_opt.numeric_value,
                        sort_order=src_opt.sort_order,
                        is_active=src_opt.is_active,
                        metadata_=dict(src_opt.metadata_),
                    )
                    self.session.add(new_opt)
                    await self.session.flush()
                    option_id_map[src_opt.id] = new_opt.id

            # 2) questions
            question_id_map: dict[int, int] = {}
            questions_stmt = select(Question).where(
                Question.instrument_version_id == version_id
            )
            source_questions = (await self.session.execute(questions_stmt)).scalars().all()
            for src_q in source_questions:
                new_q = Question(
                    instrument_version_id=new_version.id,
                    option_set_id=option_set_id_map.get(src_q.option_set_id)
                    if src_q.option_set_id
                    else None,
                    code=src_q.code,
                    source_code=src_q.source_code,
                    question_text=src_q.question_text,
                    short_label=src_q.short_label,
                    question_type=src_q.question_type,
                    research_role=src_q.research_role,
                    category=src_q.category,
                    is_scored=src_q.is_scored,
                    is_required_default=src_q.is_required_default,
                    sort_order=src_q.sort_order,
                    validation_rules=dict(src_q.validation_rules),
                    metadata_=dict(src_q.metadata_),
                )
                self.session.add(new_q)
                await self.session.flush()
                question_id_map[src_q.id] = new_q.id

            # 3) constructs (dos pasadas: crear todos, luego fijar parent_id)
            construct_id_map: dict[int, int] = {}
            constructs_stmt = select(Construct).where(
                Construct.instrument_version_id == version_id
            )
            source_constructs = (await self.session.execute(constructs_stmt)).scalars().all()
            for src_c in source_constructs:
                new_c = Construct(
                    instrument_version_id=new_version.id,
                    parent_id=None,
                    code=src_c.code,
                    name=src_c.name,
                    construct_type=src_c.construct_type,
                    description=src_c.description,
                    sort_order=src_c.sort_order,
                    metadata_=dict(src_c.metadata_),
                )
                self.session.add(new_c)
                await self.session.flush()
                construct_id_map[src_c.id] = new_c.id

            for src_c in source_constructs:
                if src_c.parent_id is not None:
                    new_c_id = construct_id_map[src_c.id]
                    new_parent_id = construct_id_map[src_c.parent_id]
                    new_c = await self.session.get(Construct, new_c_id)
                    new_c.parent_id = new_parent_id
            await self.session.flush()

            # 4) construct_items
            construct_items_stmt = select(ConstructItem).where(
                ConstructItem.construct_id.in_(construct_id_map.keys())
            )
            source_items = (await self.session.execute(construct_items_stmt)).scalars().all()
            for src_item in source_items:
                new_item = ConstructItem(
                    construct_id=construct_id_map[src_item.construct_id],
                    question_id=question_id_map[src_item.question_id],
                    weight=src_item.weight,
                    item_role=src_item.item_role,
                    scoring_direction=src_item.scoring_direction,
                    sort_order=src_item.sort_order,
                    metadata_=dict(src_item.metadata_),
                )
                self.session.add(new_item)

            # 5) scoring_rules
            scoring_rules_stmt = select(ScoringRule).where(
                ScoringRule.instrument_version_id == version_id
            )
            source_rules = (await self.session.execute(scoring_rules_stmt)).scalars().all()
            for src_rule in source_rules:
                new_rule = ScoringRule(
                    instrument_version_id=new_version.id,
                    question_id=question_id_map.get(src_rule.question_id)
                    if src_rule.question_id
                    else None,
                    construct_id=construct_id_map.get(src_rule.construct_id)
                    if src_rule.construct_id
                    else None,
                    rule_code=src_rule.rule_code,
                    rule_type=src_rule.rule_type,
                    parameters=dict(src_rule.parameters),
                    formula_expression=src_rule.formula_expression,
                    source_reference=src_rule.source_reference,
                    rule_version=src_rule.rule_version,
                    status=src_rule.status,
                )
                self.session.add(new_rule)

            await self.session.flush()
            await self.audit.log(
                action="INSTRUMENT_VERSION_CLONED",
                entity_type="instrument_version",
                entity_id=new_version.id,
                after_data={"source_version_id": version_id},
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(new_version)
        return new_version

    # --- Árbol del instrumento (harness §57) ----------------------------------

    async def get_tree(self, version_id: int) -> InstrumentTree:
        version = await self.get_version(version_id)
        editable_status = await InstrumentEditPolicy.evaluate_async(self.session, version.instrument, version)
        editable = editable_status.editable

        constructs_stmt = (
            select(Construct)
            .where(Construct.instrument_version_id == version_id)
            .options(
                selectinload(Construct.item_links).selectinload(ConstructItem.question),
            )
            .order_by(Construct.sort_order.asc().nulls_last(), Construct.id.asc())
        )
        all_constructs = list((await self.session.execute(constructs_stmt)).scalars().all())

        def build_node(construct: Construct) -> InstrumentTreeConstruct:
            children = [c for c in all_constructs if c.parent_id == construct.id]
            items = [
                InstrumentTreeItem(
                    id=link.question.id,
                    code=link.question.code,
                    question_text=link.question.question_text,
                    short_label=link.question.short_label,
                    question_type=link.question.question_type,
                    is_scored=link.question.is_scored,
                    research_role=link.question.research_role,
                    option_set_id=link.question.option_set_id,
                    weight=float(link.weight),
                    scoring_direction=link.scoring_direction,
                    sort_order=link.sort_order,
                )
                for link in sorted(
                    construct.item_links, key=lambda link: (link.sort_order is None, link.sort_order or 0)
                )
            ]
            return InstrumentTreeConstruct(
                id=construct.id,
                code=construct.code,
                name=construct.name,
                construct_type=construct.construct_type,
                sort_order=construct.sort_order,
                subdimensions=[build_node(child) for child in children],
                items=items,
            )

        variable_roots = [
            construct for construct in all_constructs
            if construct.construct_type == "VARIABLE" and construct.parent_id is None
        ]
        variables = []
        for variable in variable_roots:
            node = build_node(variable)
            variables.append(
                InstrumentTreeVariable(
                    id=variable.id,
                    code=variable.code,
                    name=variable.name,
                    role=(variable.metadata_ or {}).get("role", "INDEPENDENT"),
                    sort_order=variable.sort_order,
                    direct_items=node.items,
                    dimensions=node.subdimensions,
                )
            )
        return InstrumentTree(
            instrument_version_id=version_id,
            editable=editable,
            lock_reason=editable_status.reason,
            variables=variables,
        )

    # --- Matriz dimensión-item (harness §58) ----------------------------------

    async def get_matrix(self, version_id: int) -> ConstructMatrix:
        version = await self.get_version(version_id)
        editable = (await InstrumentEditPolicy.evaluate_async(self.session, version.instrument, version)).editable

        constructs_stmt = select(Construct).where(Construct.instrument_version_id == version_id)
        constructs = list((await self.session.execute(constructs_stmt)).scalars().all())
        constructs_by_id = {c.id: c for c in constructs}

        items_stmt = (
            select(ConstructItem)
            .where(ConstructItem.construct_id.in_(constructs_by_id.keys()))
            .options(selectinload(ConstructItem.question))
        )
        items = list((await self.session.execute(items_stmt)).scalars().all())

        question_ids = [item.question_id for item in items]
        variable_by_question: dict[int, str] = {}
        if question_ids:
            variables_stmt = select(Variable.question_id, Variable.code).where(
                Variable.question_id.in_(question_ids)
            )
            for question_id, code in (await self.session.execute(variables_stmt)).all():
                variable_by_question[question_id] = code

        rows: list[ConstructMatrixRow] = []
        for item in items:
            construct = constructs_by_id[item.construct_id]
            path = [construct]
            while path[-1].parent_id in constructs_by_id:
                path.append(constructs_by_id[path[-1].parent_id])
            path.reverse()
            root = path[0]
            is_variable_root = root.construct_type == "VARIABLE"
            dimension = path[1] if is_variable_root and len(path) > 1 else None
            subdimension = path[2] if is_variable_root and len(path) > 2 else None

            rows.append(
                ConstructMatrixRow(
                    question_id=item.question_id,
                    item_code=item.question.code,
                    question_text=item.question.question_text,
                    question_type=item.question.question_type,
                    is_scored=item.question.is_scored,
                    research_role=item.question.research_role,
                    variable_code=variable_by_question.get(item.question_id),
                    construct_id=construct.id,
                    construct_code=construct.code,
                    construct_name=construct.name,
                    construct_type=construct.construct_type,
                    research_variable_code=root.code if is_variable_root else None,
                    research_variable_name=root.name if is_variable_root else None,
                    dimension_code=dimension.code if dimension else None,
                    dimension_name=dimension.name if dimension else None,
                    subdimension_code=subdimension.code if subdimension else None,
                    subdimension_name=subdimension.name if subdimension else None,
                    weight=float(item.weight),
                    scoring_direction=item.scoring_direction,
                    status="EDITABLE" if editable else "LOCKED",
                )
            )

        return ConstructMatrix(instrument_version_id=version_id, editable=editable, rows=rows)
