import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image
from pydantic import ValidationError

from app.schemas import CertificateCustomizeRequest, CertificateTemplateCreate
from app.services.certificates import (
    CertificateData,
    CertificateGenerator,
    QRZone,
    TextZone,
)
from app.services.email.templates import DEFAULT_TEMPLATES, render_email, render_subject
from app.utils.security import (
    generate_random_certificate_code,
    normalize_certificate_code,
)


def test_certificate_codes_are_random_and_human_readable():
    codes = {generate_random_certificate_code("H7CTF26") for _ in range(1000)}
    assert len(codes) == 1000
    assert all(
        re.fullmatch(r"H7CTF26-[A-HJ-NP-Z2-9]{4}(?:-[A-HJ-NP-Z2-9]{4}){2}", code)
        for code in codes
    )
    with pytest.raises(ValueError):
        generate_random_certificate_code("bad prefix")


def test_certificate_code_normalization():
    assert (
        normalize_certificate_code(" h7ctf26 - abcd - efgh - jklm ")
        == "H7CTF26-ABCD-EFGH-JKLM"
    )


def test_certificate_name_is_normalized_and_bounded():
    assert (
        CertificateCustomizeRequest(display_name="  Abu   Rahman  ").display_name
        == "Abu Rahman"
    )
    with pytest.raises(ValidationError):
        CertificateCustomizeRequest(display_name=" ")
    with pytest.raises(ValidationError):
        CertificateCustomizeRequest(display_name="x" * 81)


def test_template_zone_validation():
    CertificateTemplateCreate(
        name="Participation",
        certificate_prefix="H7CTF26",
        text_zones=[
            {
                "field": "participant_name",
                "x": 50,
                "y": 40,
                "width": 70,
                "font_size": 54,
            }
        ],
        qr_zone={"x": 50, "y": 68, "size": 11},
    )
    with pytest.raises(ValidationError):
        CertificateTemplateCreate(
            name="Invalid",
            text_zones=[{"field": "participant_name", "x": 101, "y": 40}],
        )


def test_renderer_uses_the_persisted_certificate_id(tmp_path: Path):
    template_path = tmp_path / "template.png"
    Image.new("RGB", (1200, 700), "white").save(template_path)
    code = "H7CTF26-ABCD-EFGH-JKLM"
    generator = CertificateGenerator(
        fonts_dir=str(tmp_path), output_dir=str(tmp_path / "out")
    )
    result = generator.generate_png(
        str(template_path),
        CertificateData(
            participant_id=uuid4(),
            display_name="Abu Rahman",
            verification_code=code,
            event_name="H7CTF 2026",
            issued_at=datetime(2026, 9, 27, tzinfo=timezone.utc),
        ),
        [
            TextZone(
                id="name",
                field="participant_name",
                x=50,
                y=40,
                width=70,
                height=10,
                font_size=54,
            ),
            TextZone(
                id="id",
                field="verification_suffix",
                x=60,
                y=62,
                width=25,
                height=5,
                font_size=24,
                alignment="left",
            ),
        ],
        QRZone(x=50, y=68, size=11),
        "https://app.h7tex.com/verify",
    )
    assert result.success
    assert result.verification_code == code
    assert Path(result.file_path).name == f"{code}.png"
    assert Path(result.file_path).is_file()

    pdf_result = generator.generate_pdf(
        str(template_path),
        CertificateData(
            participant_id=uuid4(),
            display_name="Christopher Alexander Maximilian Montgomery-Wellington",
            verification_code=code,
            event_name="H7CTF 2026",
            issued_at=datetime(2026, 9, 27, tzinfo=timezone.utc),
        ),
        [
            TextZone(
                id="name",
                field="participant_name",
                x=50,
                y=40,
                width=70,
                height=10,
                font_size=54,
            )
        ],
        QRZone(x=50, y=68, size=11),
        "https://app.h7tex.com/verify",
    )
    assert pdf_result.success
    assert Path(pdf_result.file_path).name == f"{code}.pdf"
    assert Path(pdf_result.file_path).is_file()


def test_certificate_email_template_renders_portal_link():
    template = DEFAULT_TEMPLATES["certificate_available"]
    context = {
        "name": "Abu Rahman",
        "event_name": "H7CTF 2026",
        "certificate_url": "https://app.h7tex.com/portal/certificates",
    }
    subject = render_subject(template["subject"], context)
    html, text = render_email(template["body_html"], context, template["body_text"])
    assert subject == "Your H7CTF 2026 participation certificate is ready"
    assert context["certificate_url"] in html
    assert context["certificate_url"] in text
