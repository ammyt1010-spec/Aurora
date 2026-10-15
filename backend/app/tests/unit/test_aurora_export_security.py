"""Spreadsheet formula hardening and portable Power BI import format."""
import csv
import io
import json
import zipfile

from app.services.export_service import spreadsheet_safe, ExportService


def test_spreadsheet_formulas_are_neutralized():
    for attack in ("=1+1", "+cmd", "-cmd", "@SUM(1)", "  =SUM(A1:A2)", "\\t=1+1"):
        assert spreadsheet_safe(attack).startswith("'")
    assert spreadsheet_safe("Analista") == "Analista"
    assert spreadsheet_safe(7) == 7
    assert spreadsheet_safe(None) is None


def test_powerbi_bundle_can_be_imported_without_proprietary_file(tmp_path, monkeypatch):
    class Settings:
        export_storage_dir = str(tmp_path)
    monkeypatch.setattr("app.services.export_service.get_settings", lambda: Settings())
    service = ExportService.__new__(ExportService)
    path = service._write_file("test-powerbi", "POWERBI",
                               [{"value": "=EVIL", "count": 2}], ["value", "count"])
    with zipfile.ZipFile(path) as archive:
        assert {"dataset.csv", "data_dictionary.json", "LEEME.txt"} <= set(archive.namelist())
        content = archive.read("dataset.csv").decode("utf-8-sig")
        data = list(csv.DictReader(io.StringIO(content)))
        assert data[0]["value"].startswith("'")
        assert json.loads(archive.read("data_dictionary.json"))["rows"] == 1
