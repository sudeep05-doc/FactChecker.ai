"""Lightweight page-by-page PDF text and optional image extraction."""

import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from pypdf import PdfReader
from pypdf.errors import PdfReadError, PdfStreamError

from app.cal.schemas import AcquisitionStatus, CALResult
from app.preprocessing.pdf_schema import (
    PDFPageText,
    PDFPreprocessingIssue,
    PDFPreprocessingResult,
    PDFPreprocessingStatus,
)


class PDFPreprocessor:
    """Extract PDF content without loading all page content at once."""

    def __init__(self, extract_images: bool = False) -> None:
        self.extract_images = extract_images

    def process(self, content: CALResult) -> PDFPreprocessingResult:
        source = _pdf_source(content)
        base = {
            "request_id": content.request_id,
            "input_type": content.input_type,
            "source": source,
        }

        if content.acquisition_status != AcquisitionStatus.COMPLETED:
            return self._failure(
                base,
                "ACQUISITION_INCOMPLETE",
                "CAL content was not acquired successfully.",
            )

        if not source or not Path(source).is_file():
            return self._failure(
                base,
                "PDF_NOT_FOUND",
                "The acquired PDF path does not exist.",
            )

        try:
            reader = PdfReader(source, strict=False)
            if reader.is_encrypted:
                decrypt_result = reader.decrypt("")
                if not decrypt_result:
                    return self._failure(
                        base,
                        "PASSWORD_PROTECTED_PDF",
                        "The PDF is password-protected and no usable password was provided.",
                    )

            page_count = len(reader.pages)
            pages: List[PDFPageText] = []
            extracted_image_paths: List[str] = []
            warnings: List[PDFPreprocessingIssue] = []

            for page_number, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text() or ""
                pages.append(PDFPageText(page_number=page_number, text=page_text))

                if self.extract_images:
                    self._extract_page_images(
                        page,
                        source,
                        page_number,
                        extracted_image_paths,
                        warnings,
                    )

            extracted_text = "\n\n".join(
                page.text for page in pages if page.text
            )
            if page_count == 0:
                warnings.append(
                    PDFPreprocessingIssue(
                        code="EMPTY_PDF",
                        message="The PDF contains no pages.",
                    )
                )
            elif not extracted_text and not extracted_image_paths:
                warnings.append(
                    PDFPreprocessingIssue(
                        code="NO_EXTRACTABLE_CONTENT",
                        message="No text or extracted images were found in the PDF.",
                    )
                )

            return PDFPreprocessingResult(
                **base,
                extracted_text=extracted_text,
                page_count=page_count,
                pages=pages,
                extracted_image_paths=extracted_image_paths,
                metadata=_metadata(reader, source),
                preprocessing_status=PDFPreprocessingStatus.COMPLETED,
                warnings=warnings,
            )
        except (PdfReadError, PdfStreamError, OSError, ValueError, KeyError) as error:
            return self._failure(
                base,
                "CORRUPTED_PDF",
                f"The PDF could not be read safely: {error}.",
            )

    def _extract_page_images(
        self,
        page: Any,
        source: str,
        page_number: int,
        extracted_paths: List[str],
        warnings: List[PDFPreprocessingIssue],
    ) -> None:
        try:
            page_images = getattr(page, "images", [])
            for image_index, image in enumerate(page_images, start=1):
                suffix = Path(getattr(image, "name", "")).suffix or ".bin"
                temporary_file = tempfile.NamedTemporaryFile(
                    prefix=f"factchecker-pdf-page-{page_number}-{image_index}-",
                    suffix=suffix,
                    delete=False,
                )
                with temporary_file:
                    temporary_file.write(image.data)
                extracted_paths.append(temporary_file.name)
        except (OSError, AttributeError, ValueError) as error:
            warnings.append(
                PDFPreprocessingIssue(
                    code="IMAGE_EXTRACTION_FAILED",
                    message=f"An image on PDF page {page_number} could not be extracted: {error}.",
                )
            )

    @staticmethod
    def _failure(base: Dict[str, Any], code: str, message: str) -> PDFPreprocessingResult:
        return PDFPreprocessingResult(
            **base,
            preprocessing_status=PDFPreprocessingStatus.FAILED,
            errors=[PDFPreprocessingIssue(code=code, message=message)],
        )


def _pdf_source(content: CALResult) -> str:
    metadata_source = content.metadata.get("file_path")
    return str(metadata_source or content.source or "")


def _metadata(reader: PdfReader, source: str) -> Dict[str, Any]:
    document_metadata: Dict[str, str] = {}
    for key, value in (reader.metadata or {}).items():
        if value is not None:
            document_metadata[str(key)] = str(value)

    return {
        "file_name": Path(source).name,
        "file_size_bytes": Path(source).stat().st_size,
        "encrypted": reader.is_encrypted,
        "document": document_metadata,
    }