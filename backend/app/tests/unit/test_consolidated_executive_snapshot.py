from io import BytesIO
from types import SimpleNamespace

from pypdf import PdfReader

from app.services.consolidated_bundle_service import build_executive_cover, verified_executive_snapshot


def test_cover_only_uses_run_bound_snapshot():
    snapshot = {
        'source': 'persisted_scoring_run', 'analysis_run_id': 11,
        'instrument_version_id': 3, 'barem_id': 4, 'n_completed': 27,
        'publishable_constructs': 6,
        'indicator': {'construct_name': 'Exigencias', 'mean_score': 61.5},
    }
    report = SimpleNamespace(analysis_run_id=11, study_id=1, metadata_={
        'executive_snapshot': snapshot,
        'scoring_context': {'analysis_run_id': 11, 'study_id': 1, 'privacy': {'min_publishable_n': 5}},
    })
    study = SimpleNamespace(name='Instrumento verificable')
    content = build_executive_cover('Prueba', [(study, report, 'abc', b'')])
    text = PdfReader(BytesIO(content)).pages[0].extract_text()
    assert '27' in text and '61.5/100' in text and 'Exigencias' in text
    assert 'Run 11' in text
    report.analysis_run_id = 12
    assert verified_executive_snapshot(report) is None
    content = build_executive_cover('Prueba', [(study, report, 'abc', b'')])
    text = PdfReader(BytesIO(content)).pages[0].extract_text()
    assert 'Indicadores no disponibles' in text
    assert '61.5/100' not in text
