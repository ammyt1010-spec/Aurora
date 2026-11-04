"""Contenido del reporte CENSOPAS — consume el `bundle` de
`ReportService._build_bundle` y sólo formatea: nunca recalcula nada. Cada
función de sección compone el layout llamando a `components`/`tables`/
`typography`; nunca toca color, borde o padding directamente (regla #22)."""

from __future__ import annotations

import io
from datetime import datetime
from zoneinfo import ZoneInfo

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

from .charts import build_priority_chart, build_trichotomy_chart
from .components import add_callout, add_centered_badge, add_executive_metric_cards, add_section_header, add_signature_grid
from .paginate import keep_with_next
from .tables import add_colmena_table, add_key_value_grid, add_label_value_table
from .theme import CONTENT_WIDTH_MM
from .typography import add_body, add_cover_org, add_cover_subtitle, add_cover_title, add_h2, add_h3, add_caption, add_muted

_CLASSIFICATION_LABELS = {
    "RIESGO_ALTO": "Riesgo alto",
    "FACTOR_PROTECTOR": "Factor protector",
    "RIESGO_MEDIO": "Riesgo medio",
    "REVISION": "Requiere revisión",
}
_CLASSIFICATION_STATUS = {
    "RIESGO_ALTO": "red",
    "FACTOR_PROTECTOR": "green",
    "RIESGO_MEDIO": "gold",
    "REVISION": "gold",
}
_ACTION_STATUS = {
    "Aprobado": "green",
    "Completado": "green",
    "DONE": "green",
    "COMPLETED": "green",
    "Pendiente": "gold",
    "PENDING": "gold",
    "En progreso": "gold",
    "IN_PROGRESS": "gold",
    "Vencido": "red",
    "OVERDUE": "red",
    "Bloqueado": "red",
    "BLOCKED": "red",
}

_VERSION_LABELS = {"SHORT": "Corta", "MEDIUM": "Media"}
_STUDY_STATUS_LABELS = {"OPEN": "En curso", "CLOSED": "Cerrado", "DRAFT": "Borrador", "ARCHIVED": "Archivado"}


def _human_label(value: object, labels: dict[str, str]) -> str:
    if value is None or str(value).strip() == "":
        return "—"
    return labels.get(str(value).upper(), str(value).replace("_", " ").capitalize())


def build_document_content(document, bundle: dict) -> None:
    numbering = _section_numbering()

    study = bundle.get("study") or {}
    cover = bundle.get("cover") or {}
    traceability = bundle.get("traceability") or {}
    min_publishable_n = (traceability.get("privacy") or {}).get("min_publishable_n")
    version_kind = cover.get("version_kind")
    is_censopas = bundle.get("is_censopas", True)
    template = bundle.get("report_template") or {}
    if not study.get("instrument_name") and cover.get("instrument_label"):
        study = {**study, "instrument_name": cover["instrument_label"]}
    selected = set(bundle.get("sections") or [])

    def include(*keys: str) -> bool:
        return not selected or bool(selected.intersection(keys))

    if include("portada"):
        _add_cover(document, cover, study, is_censopas=is_censopas, template=template, logo_png=bundle.get("brand_logo_png"))
    if include("resumen_ejecutivo"):
        _add_executive_summary(document, next(numbering), bundle.get("executive_summary"))
    if include("ficha_tecnica"):
        _add_ficha_tecnica(
            document, next(numbering), study, bundle.get("data_quality"),
            bundle.get("methodological_label"), traceability.get("barem"), min_publishable_n,
            is_censopas=is_censopas,
        )
    if include("calidad_datos"):
        _add_data_quality_section(document, next(numbering), bundle.get("data_quality"))
    if include("variables_descriptivas") and bundle.get("sociolaboral_profile"):
        _add_sociolaboral_section(document, next(numbering), bundle["sociolaboral_profile"])

    if is_censopas:
        if include("dimensiones", "resultados_globales"):
            add_section_header(document, next(numbering), "Resultados por dimensión (D1-D6)")
            _add_trichotomy_section(document, bundle.get("dimension_results") or [], min_publishable_n)
        if version_kind == "MEDIUM" and include("subdimensiones"):
            add_section_header(document, next(numbering), "Resultados por subdimensión (S1-S20)")
            _add_trichotomy_section(document, bundle.get("subdimension_results") or [], min_publishable_n, compact=True)
        if include("dimensiones", "resultados_globales", "subdimensiones"):
            _add_interpretation_section(document, bundle.get("interpretation") or [])
            _add_priority_ranking_section(document, next(numbering), bundle.get("priority_ranking") or [])
    elif include("dimensiones", "resultados_globales", "subdimensiones"):
        add_section_header(document, next(numbering), "Resultados por constructo")
        _add_generic_construct_section(document, bundle.get("barem_results") or {})

    if include("hallazgos_premium") and (bundle.get("analysis_results") or bundle.get("premium_analytics")):
        add_section_header(document, next(numbering), "Hallazgos estadísticos complementarios")
        _add_statistical_findings(
            document,
            bundle.get("analysis_results") or [],
            bundle.get("premium_analytics") or {},
        )
    if include("plan_accion"):
        _add_action_plan_section(document, next(numbering), bundle.get("action_plans") or [])
    if include("conclusiones", "resumen_ejecutivo"):
        _add_conclusions_section(document, bundle.get("conclusions") or [])
    if include("anexos", "trazabilidad"):
        _add_traceability_appendix(document, next(numbering), traceability)
    if include("firmas", "anexos") or bundle.get("signatories"):
        _add_signatures_section(document, next(numbering), bundle.get("signatories") or [], bool(bundle.get("signatures_attested")))


def _add_generic_construct_section(document, barem_results: dict) -> None:
    """Render multidisciplinario desde el overview privado, sin tricotomía CENSOPAS.

    La API de scoring ya suprime puntuaciones y bandas para grupos con n
    insuficiente; el render no debe reconstruir esos valores desde respuestas.
    """
    results = barem_results.get("results") or []
    if not results:
        add_body(document, "No hay resultados colectivos publicables o no se ha ejecutado el análisis.")
        return
    rows = []
    for result in results:
        suppressed = bool(result.get("suppressed"))
        bands = result.get("bands") or []
        if suppressed:
            score_label = "Suprimido"
            category_label = "No publicable"
            n_label = "—"
        else:
            score = result.get("mean_score")
            score_label = f"{float(score):.2f}" if score is not None else "Sin puntuación"
            n_label = str(result.get("n_valid") or "—")
            active_bands = [band for band in bands if band.get("pct") is not None]
            if active_bands:
                top = max(active_bands, key=lambda band: float(band.get("pct") or 0))
                category_label = f"{top.get('label') or top.get('classification_code') or 'Categoría'} ({float(top['pct']):.1f} %)"
            else:
                category_label = "Sin clasificación verificable"
        rows.append([
            str(result.get("construct_name") or result.get("construct_code") or "—"),
            n_label,
            score_label,
            category_label,
        ])
    add_colmena_table(
        document,
        ["Constructo", "n válido", "Media", "Categoría predominante"],
        rows,
        widths_mm=[63, 21, 25, 69],
    )
    add_muted(document, "Las categorías son descriptivas y dependen del baremo específico. Los resultados suprimidos no se publican.")


def _section_numbering():
    n = 0
    while True:
        n += 1
        yield f"{n:02d}"


# ---------------------------------------------------------------------------
# Portada
# ---------------------------------------------------------------------------

def _add_cover(document, cover: dict, study: dict, *, is_censopas: bool = True, template: dict | None = None, logo_png: bytes | None = None) -> None:
    template = template or {}
    badge_text = cover.get("badge_text") or "EXPEDIENTE TÉCNICO · BORRADOR CONTROLADO"
    add_centered_badge(document, badge_text[:110], width_mm=110, height_mm=9)
    document.add_paragraph().paragraph_format.space_after = Pt(10)

    if logo_png:
        logo_paragraph = document.add_paragraph()
        logo_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        logo_paragraph.add_run().add_picture(io.BytesIO(logo_png), width=Cm(3.8))
        logo_paragraph.paragraph_format.space_after = Pt(12)

    default_title = (
        "Informe técnico de evaluación de riesgos psicosociales"
        if is_censopas else "Informe técnico de evaluación ocupacional"
    )
    add_cover_title(document, str(template.get("header_title") or default_title)[:180])

    org = cover.get("organization_name")
    if org:
        add_cover_org(document, org)
    if study.get("name"):
        add_cover_subtitle(document, str(study["name"])[:180])

    label = cover.get("methodological_label") or {}
    if is_censopas:
        mode_label = (
            f"{label.get('label', 'Baremo de referencia')} — "
            + ("Equivalente al resultado oficial CENSOPAS-COPSOQ" if label.get("official_equivalence")
               else "Resultados sin equivalencia oficial CENSOPAS-COPSOQ")
        )
    else:
        mode_label = f"Instrumento: {cover.get('instrument_label') or study.get('instrument_name') or 'Evaluación profesional'}"
    add_cover_subtitle(document, mode_label)

    pairs = [
        ("RUC", cover.get("ruc") or study.get("ruc") or "—"),
        ("Población", str(cover.get("population") or study.get("population") or "No registrada")),
        ("Tipo de organización", cover.get("activity") or "No registrado"),
        ("Versión", _human_label(cover.get("version_kind"), _VERSION_LABELS)),
        ("Estado", _human_label(study.get("status"), _STUDY_STATUS_LABELS)),
        ("Privacidad", "Sin respuestas individuales · n mínimo protegido"),
        ("Código de estudio", cover.get("study_code") or study.get("code") or "—"),
        ("Emisión", _format_datetime(cover.get("generated_at")) or "—"),
    ]
    add_key_value_grid(document, pairs, widths_mm=[28, 61, 28, 61])
    document.add_paragraph().paragraph_format.space_after = Pt(14)

    add_callout(
        document,
        cover.get("confidentiality_notice")
        or "Documento para revisión del profesional responsable, psicología ocupacional, "
        "seguridad y representante de la empresa. No establece diagnósticos individuales "
        "ni inferencias causales.",
        variant="neutral",
    )

    document.add_page_break()


# ---------------------------------------------------------------------------
# Ficha técnica
# ---------------------------------------------------------------------------


def _add_ficha_tecnica(document, number, study, data_quality, methodological_label, barem, min_publishable_n, *, is_censopas=True) -> None:
    add_section_header(document, number, "Ficha técnica")
    data_quality = data_quality or {}
    label = methodological_label or {}
    period = " – ".join(filter(None, [_format_datetime(study.get("period_start")), _format_datetime(study.get("period_end"))])) or "—"
    pairs = [
        ("Instrumento", study.get("instrument_name") or ("CENSOPAS-COPSOQ" if is_censopas else "Instrumento de evaluación")),
        ("Versión del instrumento", study.get("instrument_version_code") or "—"),
        ("Estudio", study.get("name") or "—"),
        ("Tipo de estudio", _human_label(study.get("study_type"), {})),
        ("Estado", _human_label(study.get("status"), _STUDY_STATUS_LABELS)),
        ("Población convocada", str(data_quality["invited_count"]) if data_quality.get("invited_count") is not None else "No disponible en el sistema"),
        ("Respondieron (sesiones)", str(data_quality.get("started_count", "—"))),
        ("Válidos", str(data_quality.get("valid_count", "—"))),
        ("Excluidos", str(data_quality.get("excluded_count", "—"))),
        ("Tasa válida", _format_percentage(data_quality.get("completion_rate"))),
        ("Período", period),
        ("Baremo aplicado", (barem or {}).get("name") or "—"),
        ("Equivalencia oficial", ("Habilitada" if label.get("official_equivalence") else "No habilitada") if is_censopas else "No aplica"),
        ("N mínimo publicable", str(min_publishable_n) if min_publishable_n is not None else "—"),
    ]
    add_key_value_grid(document, pairs, widths_mm=[38, 51, 38, 51])
    document.add_paragraph().paragraph_format.space_after = Pt(8)


def _add_executive_summary(document, number, summary: dict | None) -> None:
    if not summary:
        return
    add_section_header(document, number, "Resumen ejecutivo")
    add_body(document, summary.get("headline") or "—")

    add_executive_metric_cards(document, [
        ("Respuestas válidas", str(summary["n_valid"]) if summary.get("n_valid") is not None else "No disponible"),
        ("Finalización", _format_percentage(summary.get("completion_rate"))),
        ("Prioridades de revisión", str(len(summary.get("priority_dimensions") or []))),
    ])

    priority_dimensions = summary.get("priority_dimensions") or []
    if priority_dimensions:
        lead = priority_dimensions[0]
        add_callout(
            document,
            f"Foco inicial para gerencia: {lead.get('construct_name') or lead.get('construct_code') or '—'} "
            f"({_format_pct(lead.get('unfavorable_pct'))} de respuestas desfavorables). "
            "Corresponde a una prioridad relativa de revisión; la clasificación colectiva se muestra por separado.",
            variant="warning",
        )
        document.add_paragraph().paragraph_format.space_after = Pt(4)
        add_h3(document, "Dimensiones prioritarias")
        _insert_chart(document, build_priority_chart(priority_dimensions))
        add_caption(document, "Porcentaje de respuestas desfavorables. Los niveles corresponden a los baremos del instrumento.")
        rows = []
        for dimension in priority_dimensions:
            label = dimension.get("construct_name") or dimension.get("construct_code") or "—"
            classification = dimension.get("classification")
            rows.append([label, _format_pct(dimension.get("unfavorable_pct")), _CLASSIFICATION_LABELS.get(classification, classification or "—")])
        add_colmena_table(document, ["Dimensión", "% Desfavorable", "Clasificación"], rows, widths_mm=[88, 45, 45])
    if summary.get("official_equivalence") is False:
        add_caption(document, "El baremo de esta muestra es de referencia: estos resultados no tienen equivalencia oficial CENSOPAS-COPSOQ.")
    document.add_paragraph()


def _add_data_quality_section(document, number, data_quality: dict | None) -> None:
    if not data_quality:
        return
    add_section_header(document, number, "Calidad de datos")
    pairs = [
        ("Sesiones iniciadas", str(data_quality.get("started_count", "—"))),
        ("Completadas", str(data_quality.get("completed_count", "—"))),
        ("Válidas", str(data_quality.get("valid_count", "—"))),
        ("Abandonadas", str(data_quality.get("abandoned_count", "—"))),
        ("En revisión", str(data_quality.get("review_count", "—"))),
        ("Excluidas", str(data_quality.get("excluded_count", "—"))),
        ("Tasa de finalización", _format_percentage(data_quality.get("completion_rate"))),
        ("Duración promedio", _format_duration(data_quality.get("avg_duration_seconds"))),
    ]
    add_key_value_grid(document, pairs, widths_mm=[38, 51, 38, 51])
    document.add_paragraph().paragraph_format.space_after = Pt(4)
    add_caption(document, "Los porcentajes se calculan sobre sesiones iniciadas; no incluyen identidad de los respondientes.")
    document.add_paragraph()


def _add_sociolaboral_section(document, number, profile: list[dict]) -> None:
    add_section_header(document, number, "Perfil sociolaboral")
    if not profile:
        add_body(document, "Este estudio no tiene variables sociolaborales descriptivas provisionadas.")
        return
    add_body(
        document,
        "Variables descriptivas (sexo, edad, instrucción, puesto, área, contrato, antigüedad, "
        "horario, horas, tipo de sueldo, rango remunerativo). No forman parte del puntaje psicosocial.",
    )
    rows = []
    for question in profile:
        for category in question.get("categories") or []:
            label = question.get("label") or question.get("code") or "—"
            cat_label = category.get("label") or "—"
            if category.get("suppressed"):
                rows.append([label, cat_label, "Oculto", "Oculto"])
            else:
                rows.append([label, cat_label, str(category.get("n", "—")), _format_pct(category.get("percentage"))])
    add_colmena_table(document, ["Variable", "Categoría", "n", "%"], rows, widths_mm=[54, 70, 27, 27], compact=True)
    document.add_paragraph()


# ---------------------------------------------------------------------------
# Resultados D1-D6 / S1-S20
# ---------------------------------------------------------------------------

def _add_trichotomy_section(document, results: list[dict], min_publishable_n, *, compact: bool = False) -> None:
    if not results:
        add_body(document, "Este estudio todavía no tiene resultados calculados para este bloque.")
        return

    headers = ["Constructo", "Favorable n (%)", "Intermedio n (%)", "Desfavorable n (%)", "n válido", "Clasificación"]
    widths = [46, 26, 26, 26, 20, 34]
    rows = []
    for result in results:
        code = result.get("construct_code")
        name = result.get("construct_name") or "—"
        label = f"{code} · {name}" if code else name
        if result.get("suppressed"):
            hidden = f"Oculto (n<{min_publishable_n})" if min_publishable_n else "Oculto"
            rows.append([label, hidden, hidden, hidden, hidden, hidden])
            continue
        cells = [label]
        for key in ("favorable_pct", "intermediate_pct", "unfavorable_pct"):
            n_key = key.replace("_pct", "_n")
            pct = result.get(key)
            n = result.get(n_key)
            cells.append(f"{n if n is not None else '—'} ({_format_pct(pct)})")
        cells.append(str(result.get("n_valid", "—")))
        classification = result.get("collective_classification")
        cells.append(_CLASSIFICATION_LABELS.get(classification, classification or "—"))
        rows.append(cells)

    table = add_colmena_table(document, headers, rows, widths_mm=widths, compact=compact)
    for row_index, result in enumerate(results):
        classification = result.get("collective_classification")
        status = _CLASSIFICATION_STATUS.get(classification)
        if status and not result.get("suppressed"):
            cell = table.rows[row_index + 1].cells[5]
            label = _CLASSIFICATION_LABELS.get(classification, classification or "—")
            _render_status(cell, label, status)

    document.add_paragraph()
    if not compact:
        _insert_chart(document, build_trichotomy_chart(results))


def _render_status(cell, label: str, status: str) -> None:
    from .cells import render_status_cell

    render_status_cell(cell, label=label, status=status)


def _add_interpretation_section(document, entries: list[dict]) -> None:
    if not entries:
        return
    add_h2(document, "Lectura e hipótesis para revisión")
    add_body(
        document,
        "Las distribuciones describen exposición colectiva. La causa de cada resultado requiere contraste "
        "con las condiciones de trabajo y el Comité o Grupo de Trabajo; no se infiere causalidad ni diagnóstico individual.",
    )
    with_hypotheses = [entry for entry in entries if entry.get("origin_hypothesis")]
    if with_hypotheses:
        rows = [
            [entry.get("construct_name") or entry.get("construct_code") or "—",
             "; ".join(entry["origin_hypothesis"]),
             "; ".join(entry.get("preventive_orientation") or []) or "Pendiente de definición"]
            for entry in with_hypotheses
        ]
        add_colmena_table(document, ["Dimensión", "Hipótesis a contrastar", "Orientación preventiva"], rows, widths_mm=[48, 65, 65], compact=True)
    else:
        add_caption(document, "No se registraron hipótesis de origen contrastadas para este estudio; el informe no atribuye causas.")
    document.add_paragraph()


def _add_priority_ranking_section(document, number, ranking: list[dict]) -> None:
    add_section_header(document, number, "Priorización preventiva")
    add_body(
        document,
        "El siguiente orden es una ayuda de priorización preventiva calculada por el backend "
        "(% desfavorable); no es una clasificación oficial adicional de CENSOPAS-COPSOQ ni "
        "reemplaza el juicio técnico del Comité/Grupo de Trabajo.",
    )
    if not ranking:
        add_body(document, "Sin dimensiones publicables para priorizar todavía.")
        return
    _insert_chart(document, build_priority_chart(ranking))
    add_caption(document, "Visualización de porcentajes desfavorables, no una nueva clasificación oficial.")
    rows = []
    for row in ranking:
        classification = row.get("collective_classification")
        rows.append([
            str(row.get("priority_rank") or "—"),
            f"{row.get('construct_code') or ''} · {row.get('construct_name') or '—'}",
            _format_pct(row.get("unfavorable_pct")),
            str(row.get("n_valid") or "—"),
            _CLASSIFICATION_LABELS.get(classification, classification or "—"),
        ])
    table = add_colmena_table(document, ["Prioridad", "Constructo", "% Desfavorable", "n válido", "Clasificación"], rows, widths_mm=[22, 60, 32, 24, 40])
    for row_index, row in enumerate(ranking):
        status = _CLASSIFICATION_STATUS.get(row.get("collective_classification"))
        if status:
            label = _CLASSIFICATION_LABELS.get(row.get("collective_classification"), "—")
            _render_status(table.rows[row_index + 1].cells[4], label, status)
    document.add_paragraph()


def _add_conclusions_section(document, conclusions: list[str]) -> None:
    add_h2(document, "Conclusiones")
    if not conclusions:
        add_body(document, "Sin datos suficientes para conclusiones todavía.")
        return
    for line in conclusions:
        document.add_paragraph(line, style="List Bullet")
    document.add_paragraph()


def _add_statistical_findings(document, analysis_results: list[dict], premium: dict) -> None:
    """Lectura auditable de los análisis disponibles, sin duplicar volcados crudos.

    Se muestran únicamente valores presentes en el bundle; la sección no
    establece causalidad, no crea umbrales oficiales ni publica clusters.
    """
    if not analysis_results:
        add_body(document, "No hay análisis estadísticos complementarios disponibles para este estudio.")
        return

    add_body(
        document,
        "Estos análisis complementan la descripción colectiva del instrumento. "
        "No modifican sus categorías de exposición ni sustituyen la revisión del profesional responsable.",
    )

    reliability = [r for r in analysis_results if r.get("result_type") in {"CRONBACH_ALPHA", "MCDONALD_OMEGA"}]
    if reliability:
        add_h2(document, "Consistencia interna")
        rows = []
        for result in sorted(reliability, key=lambda r: (r.get("result_code") or "", r.get("result_type") or "")):
            value = result.get("numeric_value")
            reading = "Revisar ítems y codificación" if value is not None and value < 0 else "Interpretar con el contenido de los ítems"
            rows.append([
                result.get("result_code") or "—",
                "Alfa de Cronbach" if result.get("result_type") == "CRONBACH_ALPHA" else "Omega de McDonald",
                str(result.get("n_valid") or "—"),
                _format_number(value),
                reading,
            ])
        add_colmena_table(document, ["Escala", "Indicador", "n", "Valor", "Lectura técnica"], rows, widths_mm=[20, 42, 14, 20, 82], compact=True)
        add_caption(document, "La consistencia interna no demuestra por sí sola validez de constructo. Los valores negativos requieren revisión antes de interpretarse.")

    normality = [r for r in analysis_results if r.get("result_type") == "NORMALITY" and r.get("p_value") is not None]
    if normality:
        rejected = sum(float(r["p_value"]) < 0.05 for r in normality)
        add_h2(document, "Distribución y elección de pruebas")
        add_body(
            document,
            f"En {rejected} de {len(normality)} contrastes de normalidad se obtuvo p < 0,05. "
            "La interpretación de comparaciones debe considerar la escala, el tamaño de grupo y la forma de la distribución; "
            "no se selecciona una prueba únicamente por este valor p.",
        )
        add_colmena_table(
            document, ["Dimensión", "n", "Estadístico", "p"],
            [[r.get("result_code") or "—", str(r.get("n_valid") or "—"),
              _format_number(r.get("statistic_value")), _format_number(r.get("p_value"), 4)] for r in normality],
            widths_mm=[50, 25, 52, 51], compact=True,
        )

    comparisons = [r for r in analysis_results if r.get("result_type") in {"CHI_SQUARE", "MANN_WHITNEY", "KRUSKAL_WALLIS"}]
    if comparisons:
        add_h2(document, "Comparaciones entre grupos")
        names = {"CHI_SQUARE": "Chi-cuadrado", "MANN_WHITNEY": "Mann-Whitney", "KRUSKAL_WALLIS": "Kruskal-Wallis"}
        add_colmena_table(
            document, ["Contraste", "Prueba", "n", "p", "Efecto"],
            [[r.get("result_code") or "—", names[r["result_type"]], str(r.get("n_valid") or "—"),
              _format_number(r.get("p_value"), 4), _format_number(r.get("effect_size"))] for r in comparisons[:12]],
            widths_mm=[50, 45, 18, 27, 38], compact=True,
        )
        add_caption(document, "Las comparaciones son descriptivas/exploratorias; interpretar tamaño del efecto, grupos y multiplicidad de pruebas antes de adoptar medidas.")

    correlations = [r for r in analysis_results if r.get("result_type") == "SPEARMAN" and r.get("statistic_value") is not None]
    if correlations:
        add_h2(document, "Asociaciones entre dimensiones")
        premium_by_code = {
            r.get("result_code"): r for r in premium.get("results") or []
            if r.get("result_type") == "SPEARMAN"
        }
        strongest = sorted(correlations, key=lambda r: abs(float(r["statistic_value"])), reverse=True)[:6]
        rows = []
        adjusted_available = False
        significant_adjusted = 0
        for result in strongest:
            adjustment = premium_by_code.get(result.get("result_code")) or {}
            adjusted = adjustment.get("adjusted_p_value")
            adjusted_available = adjusted_available or adjusted is not None
            significant_adjusted += adjusted is not None and float(adjusted) < 0.05
            rows.append([
                (result.get("result_code") or "—").replace("_x_", " × "),
                str(result.get("n_valid") or "—"),
                _format_number(result.get("statistic_value")),
                _format_number(result.get("p_value"), 4),
                _format_number(adjusted, 4),
            ])
        add_colmena_table(document, ["Par", "n", "ρ Spearman", "p", "p ajustado"], rows, widths_mm=[46, 22, 38, 34, 38], compact=True)
        if adjusted_available:
            add_body(
                document,
                f"Entre las {len(strongest)} asociaciones de mayor magnitud mostradas, "
                f"{significant_adjusted} conservaron p ajustado < 0,05. "
                "La asociación no demuestra causalidad.",
            )
        else:
            add_caption(document, "No se dispone de p ajustado para estas asociaciones; los valores p sin corrección son exploratorios.")

    if any(r.get("result_type") == "KMEANS" for r in analysis_results):
        add_callout(document, "El agrupamiento calculado es exploratorio. No se publican asignaciones individuales ni se utiliza para decisiones laborales sobre personas.", variant="neutral")


def _add_action_plan_section(document, number, plans: list[dict]) -> None:
    add_section_header(document, number, "Plan de acción y seguimiento")
    if not plans:
        add_body(document, "No hay planes de acción registrados para este estudio.")
        return
    for plan in plans:
        heading = add_h3(document, plan.get("name") or "Plan de acción")
        keep_with_next(heading)
        approval = "Aprobado" if plan.get("approved") else "Pendiente de aprobación"
        add_body(document, f"Estado del plan: {_human_label(plan.get('status'), {'ACTIVE': 'Activo'})}. {approval}.")

        items = plan.get("items") or []
        if not items:
            add_caption(document, "Este plan todavía no contiene medidas registradas.")
        for item in items:
            priority = item.get("priority")
            construct = " · ".join(filter(None, [item.get("construct_code"), item.get("construct_name")]))
            add_h3(document, f"{f'Prioridad {priority}' if priority is not None else 'Medida registrada'} · {construct or 'Acción preventiva'}")
            status_code = item.get("effective_status") or item.get("status")
            status_label = _human_label(status_code, {
                "IN_PROGRESS": "En progreso", "PENDING": "Pendiente", "COMPLETED": "Completada",
                "DONE": "Completada", "OVERDUE": "Vencida", "BLOCKED": "Bloqueada",
            })
            add_label_value_table(document, [
                ("Hallazgo registrado", item.get("finding") or "No registrado"),
                ("Medida propuesta", item.get("action_description") or "No registrada"),
                ("Responsable", item.get("responsible_label") or "Sin asignar"),
                ("Fecha objetivo", item.get("due_date") or "No registrada"),
                ("Seguimiento", status_label),
            ], widths_mm=[38, 140])
            if _ACTION_STATUS.get(status_code) == "red":
                add_callout(document, f"Atención: esta medida figura como {status_label.lower()}.", variant="danger")
            for kpi in item.get("kpis") or []:
                measured = kpi.get("current_value")
                if measured is None:
                    latest = kpi.get("latest_measurement") or {}
                    measured = latest.get("text_value") or "sin medición"
                add_caption(
                    document,
                    f"KPI {kpi.get('code') or '—'}: {kpi.get('name') or '—'} · "
                    f"línea base {_format_number(kpi.get('baseline_value'))} · actual {measured} · "
                    f"meta {_format_number(kpi.get('target_value'))}.",
                )
        document.add_paragraph()


def _add_traceability_appendix(document, number, traceability: dict) -> None:
    add_section_header(document, number, "Anexo de trazabilidad")
    if not traceability:
        add_body(document, "No hay metadatos de trazabilidad disponibles.")
        return
    pairs = [
        ("Versión del instrumento", traceability.get("version_kind") or "—"),
        ("Hash del manifiesto", traceability.get("manifest_hash") or "—"),
        ("Linaje", " → ".join(traceability.get("lineage") or [])),
        ("N mínimo publicable", str((traceability.get("privacy") or {}).get("min_publishable_n", "—"))),
        ("Registros individuales incluidos", "No"),
    ]
    barem = traceability.get("barem") or {}
    if barem:
        pairs.extend([
            ("Baremo", f"{barem.get('name') or '—'} · {barem.get('version') or '—'}"),
            ("Hash del baremo", barem.get("content_hash") or "—"),
            ("Fuente del baremo", barem.get("source_reference") or "—"),
        ])
    add_label_value_table(document, pairs, widths_mm=[45, CONTENT_WIDTH_MM - 45])
    document.add_paragraph()

    runs = traceability.get("analysis_runs") or []
    if runs:
        add_h3(document, "Ejecuciones analíticas")
        headers = ["Tipo", "Estado", "Motor", "Algoritmo", "Hash de entrada"]
        widths = [30, 24, 40, 34, 50]
        rows = []
        for run in runs:
            rows.append([
                run.get("analysis_type") or "—",
                run.get("status") or "—",
                " ".join(filter(None, [run.get("engine"), run.get("engine_version")])) or "—",
                run.get("algorithm_version") or "—",
                run.get("input_hash") or "—",
            ])
        add_colmena_table(document, headers, rows, widths_mm=widths, compact=True)


def _add_signatures_section(document, number, signatories: list[dict], attested: bool) -> None:
    # Firmas siempre en página propia — nunca queremos la grilla 2x2
    # partida entre dos páginas por quedar cerca del corte.
    document.add_page_break()
    add_section_header(document, number, "Firmas y conformidad")
    entries = [
        {"role": "Profesional responsable (Psicología/Salud ocupacional)"},
        {"role": "Representante de la organización"},
        {"role": "Seguridad y Salud en el Trabajo (SST)"},
        {"role": "Psicología ocupacional"},
    ]
    by_role = {entry.get("role"): entry for entry in signatories}
    entries = [{**entry, **by_role.get(entry["role"], {})} for entry in entries]
    add_muted(document, "Los nombres y las imágenes de firma fueron facilitados por la organización para esta emisión. Su inclusión no constituye una firma digital certificada ni reemplaza la revisión profesional o los requisitos formales aplicables.")
    if attested:
        add_muted(document, "La persona que generó este documento declaró contar con autorización para incorporar las imágenes de firma. La emisión queda vinculada al registro y hash del informe en AURORA.")
    add_signature_grid(document, entries)


def _insert_chart(document, image: io.BytesIO | None) -> None:
    if image is None:
        return
    document.add_picture(image, width=Cm(15.5))
    document.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER


# ---------------------------------------------------------------------------
# Formato
# ---------------------------------------------------------------------------

def _format_number(value: float | None, decimals: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value:.{decimals}f}"


def _format_pct(value: float | None, decimals: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value:.{decimals}f}%"


def _format_percentage(ratio: float | None, decimals: int = 1) -> str:
    if ratio is None:
        return "—"
    return f"{ratio * 100:.{decimals}f}%"


def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    minutes, remainder = divmod(int(seconds), 60)
    return f"{minutes} min {remainder} s" if minutes else f"{remainder} s"


def _format_datetime(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(ZoneInfo("America/Lima"))
        return parsed.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return value
