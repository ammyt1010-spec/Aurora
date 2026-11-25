"""Repara enlaces CENSOPAS oficiales incompletos sin alterar respuestas históricas.

Uso: python scripts/repair_incomplete_censopas_surveys.py [--apply]
Sin --apply solo informa los IDs y conteos. Respaldar la base antes de aplicar.
Los cuestionarios ya terminados sin ningún ítem puntuable quedan EXCLUDED;
siguen contando como recibidos en telemetría y se conservan íntegros para auditoría.
"""

from __future__ import annotations

import argparse
import hashlib
import json

from sqlalchemy import create_engine, text

from app.core.config import get_settings


SELECT_AFFECTED = text("""
    SELECT su.id AS survey_id, su.instrument_version_id AS version_id,
           array_agg(s.id ORDER BY s.id) AS study_ids,
           (SELECT count(*) FROM colmena.questions q
            WHERE q.instrument_version_id = su.instrument_version_id) AS expected_count,
           (SELECT count(*) FROM colmena.survey_questions sq
            WHERE sq.survey_id = su.id) AS linked_count
    FROM colmena.surveys su
    JOIN colmena.instrument_versions v ON v.id = su.instrument_version_id
    JOIN colmena.instruments i ON i.id = v.instrument_id
    JOIN colmena.studies s ON s.survey_id = su.id
    WHERE i.code = 'CENSOPAS_COPSOQ' AND i.is_system
      AND v.version_code IN ('SHORT-OFICIAL', 'MEDIUM-OFICIAL')
    GROUP BY su.id
    HAVING (SELECT count(*) FROM colmena.survey_questions sq
            WHERE sq.survey_id = su.id)
           < (SELECT count(*) FROM colmena.questions q
              WHERE q.instrument_version_id = su.instrument_version_id)
    ORDER BY su.id
""")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Aplicar una reparación transaccional")
    args = parser.parse_args()
    engine = create_engine(get_settings().database_url_sync)
    with engine.begin() as conn:
        affected = conn.execute(SELECT_AFFECTED).mappings().all()
        for row in affected:
            survey_id = row["survey_id"]
            version_id = row["version_id"]
            bank = conn.execute(text("""
                SELECT q.id, q.sort_order, q.is_scored
                FROM colmena.questions q
                WHERE q.instrument_version_id = :version_id
                ORDER BY q.sort_order, q.id
            """), {"version_id": version_id}).mappings().all()
            linked = set(conn.execute(text("""
                SELECT question_id FROM colmena.survey_questions WHERE survey_id = :survey_id
            """), {"survey_id": survey_id}).scalars())
            bank_ids = {question["id"] for question in bank}
            if not linked.issubset(bank_ids) or len(bank) != row["expected_count"]:
                raise RuntimeError(f"Survey {survey_id}: hay vínculos fuera del banco oficial; se aborta.")
            if any(question["is_scored"] and question["id"] in linked for question in bank):
                raise RuntimeError(
                    f"Survey {survey_id}: tiene ítems puntuables parciales; requiere revisión individual."
                )
            section_id = conn.execute(text("""
                SELECT id FROM colmena.survey_sections
                WHERE survey_id = :survey_id AND section_kind = 'INSTRUMENT'
                ORDER BY sort_order, id LIMIT 1
            """), {"survey_id": survey_id}).scalar_one_or_none()
            if section_id is None:
                raise RuntimeError(f"Survey {survey_id}: no existe sección del instrumento; se aborta.")
            missing = [question for question in bank if question["id"] not in linked]
            print(f"survey={survey_id} studies={list(row['study_ids'])} "
                  f"linked={row['linked_count']}/{row['expected_count']} missing={len(missing)}")
            if not args.apply:
                continue

            for question in missing:
                conn.execute(text("""
                    INSERT INTO colmena.survey_questions
                        (survey_id, question_id, section_id, sort_order, is_required, settings)
                    SELECT :survey_id, q.id, :section_id, q.sort_order - 1,
                           q.is_required_default, '{}'::jsonb
                    FROM colmena.questions q WHERE q.id = :question_id
                """), {"survey_id": survey_id, "section_id": section_id,
                         "question_id": question["id"]})
            conn.execute(text("""
                UPDATE colmena.survey_questions sq SET sort_order = q.sort_order - 1
                FROM colmena.questions q
                WHERE sq.survey_id = :survey_id AND q.id = sq.question_id
            """), {"survey_id": survey_id})

            for study_id in row["study_ids"]:
                original_hashes = list(conn.execute(text("""
                    SELECT sha256_hash FROM colmena.study_snapshots
                    WHERE study_id = :study_id AND snapshot_type = 'STUDY_OPEN'
                    ORDER BY id
                """), {"study_id": study_id}).scalars())
                snapshot_data = {
                    "reason": "Reparación de formulario oficial publicado sin ítems puntuables",
                    "survey_id": survey_id,
                    "instrument_version_id": version_id,
                    "original_study_open_hashes": original_hashes,
                    "question_ids_in_official_order": [question["id"] for question in bank],
                    "scored_question_count": sum(question["is_scored"] for question in bank),
                }
                serialized = json.dumps(snapshot_data, sort_keys=True)
                conn.execute(text("""
                    INSERT INTO colmena.study_snapshots
                        (study_id, snapshot_type, snapshot_data, sha256_hash)
                    VALUES (:study_id, 'STUDY_REPAIR', CAST(:data AS jsonb), :hash)
                    ON CONFLICT (study_id, snapshot_type, sha256_hash) DO NOTHING
                """), {"study_id": study_id, "data": serialized,
                         "hash": hashlib.sha256(serialized.encode()).hexdigest()})
                excluded = conn.execute(text("""
                    UPDATE colmena.response_sessions rs
                    SET validation_status = 'EXCLUDED',
                        exclusion_reason = 'Formulario anterior incompleto: no se aplicaron los ítems puntuables oficiales.'
                    WHERE rs.study_id = :study_id AND rs.status = 'COMPLETED'
                      AND rs.validation_status <> 'EXCLUDED'
                      AND NOT EXISTS (
                        SELECT 1 FROM colmena.responses r
                        JOIN colmena.questions q ON q.id = r.question_id
                        WHERE r.response_session_id = rs.id AND q.is_scored AND NOT r.is_missing
                      )
                """), {"study_id": study_id}).rowcount
                print(f"  study={study_id} historical_non_scoring_sessions_excluded={excluded}")
        print(f"affected_surveys={len(affected)} mode={'APPLY' if args.apply else 'DRY_RUN'}")


if __name__ == "__main__":
    main()
