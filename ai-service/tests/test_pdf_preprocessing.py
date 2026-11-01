from pathlib import Path

from pypdf import PdfWriter

from app.cal import AcquisitionStatus, CALResult
from app.preprocessing import PDFPreprocessor, PDFPreprocessingStatus


def make_pdf_result(path: Path) -> CALResult:
    return CALResult(
        request_id="00000000-0000-4000-8000-000000000003",
        input_type="pdf",
        source=str(path),
        metadata={"file_path": str(path)},
        acquisition_status=AcquisitionStatus.COMPLETED,
    )


def make_minimal_text_pdf(path: Path) -> None:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length 44 >>\nstream\nBT /F1 12 Tf 72 720 Td (Hello PDF) Tj ET\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, object_data in enumerate(objects, start=1):
        offsets.append(len(data))
        data.extend(f"{number} 0 obj\n".encode())
        data.extend(object_data)
        data.extend(b"\nendobj\n")
    xref_offset = len(data)
    data.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    data.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode()
    )
    path.write_bytes(data)


def test_text_pdf_extracts_page_text_and_metadata(tmp_path: Path) -> None:
    pdf_path = tmp_path / "text.pdf"
    make_minimal_text_pdf(pdf_path)

    result = PDFPreprocessor().process(make_pdf_result(pdf_path))

    assert result.preprocessing_status == PDFPreprocessingStatus.COMPLETED
    assert result.page_count == 1
    assert "Hello PDF" in result.extracted_text
    assert result.pages[0].page_number == 1
    assert result.metadata["file_name"] == "text.pdf"


def test_empty_pdf_reports_warning(tmp_path: Path) -> None:
    pdf_path = tmp_path / "empty.pdf"
    writer = PdfWriter()
    with pdf_path.open("wb") as file:
        writer.write(file)

    result = PDFPreprocessor().process(make_pdf_result(pdf_path))

    assert result.preprocessing_status == PDFPreprocessingStatus.COMPLETED
    assert result.page_count == 0
    assert result.warnings[0].code == "EMPTY_PDF"


def test_corrupted_pdf_is_reported(tmp_path: Path) -> None:
    pdf_path = tmp_path / "corrupted.pdf"
    pdf_path.write_bytes(b"not a pdf")

    result = PDFPreprocessor().process(make_pdf_result(pdf_path))

    assert result.preprocessing_status == PDFPreprocessingStatus.FAILED
    assert result.errors[0].code == "CORRUPTED_PDF"


def test_password_protected_pdf_is_reported(tmp_path: Path) -> None:
    pdf_path = tmp_path / "protected.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("secret")
    with pdf_path.open("wb") as file:
        writer.write(file)

    result = PDFPreprocessor().process(make_pdf_result(pdf_path))

    assert result.preprocessing_status == PDFPreprocessingStatus.FAILED
    assert result.errors[0].code == "PASSWORD_PROTECTED_PDF"