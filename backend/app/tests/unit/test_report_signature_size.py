"""The report API and renderer must agree on the 500 KiB signature limit."""

import base64
import io
from random import Random

import pytest
from PIL import Image
from pydantic import ValidationError

from app.core.exceptions import ValidationDomainError
from app.schemas.reports import MAX_SIGNATURE_PNG_BYTES, ReportSignatory
from app.services.report_service import ReportService


def _noise_png(side: int) -> bytes:
    image = Image.frombytes("RGB", (side, side), Random(7).randbytes(side * side * 3))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_signature_png_accepts_just_under_500_kib_and_rejects_larger_file():
    allowed = _noise_png(400)
    oversized = _noise_png(420)
    assert 450 * 1024 < len(allowed) <= MAX_SIGNATURE_PNG_BYTES
    assert len(oversized) > MAX_SIGNATURE_PNG_BYTES

    value = "data:image/png;base64," + base64.b64encode(allowed).decode("ascii")
    signatory = ReportSignatory(role="COMPANY", name="Representante", signature_png=value)
    assert ReportService._decode_png(
        signatory.signature_png, max_bytes=MAX_SIGNATURE_PNG_BYTES, label="La firma", max_pixels=4_000_000
    ) == allowed

    too_large = "data:image/png;base64," + base64.b64encode(oversized).decode("ascii")
    with pytest.raises(ValidationError):
        ReportSignatory(role="COMPANY", name="Representante", signature_png=too_large)
    with pytest.raises(ValidationDomainError):
        ReportService._decode_png(too_large, max_bytes=MAX_SIGNATURE_PNG_BYTES, label="La firma")
