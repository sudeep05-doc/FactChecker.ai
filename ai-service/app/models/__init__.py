"""Foundation model integrations."""

from app.models.text_encoder import SentenceTransformerTextEncoder, resolve_device
from app.models.text_encoder_schema import TextEncodingResult, TextEncodingStatus
from app.models.image_encoder import OpenCLIPImageEncoder
from app.models.image_encoder_schema import ImageEncodingResult, ImageEncodingStatus
from app.models.whisper_schema import TranscriptionResult, TranscriptionStatus
from app.models.whisper_transcriber import WhisperTranscriber
from app.models.ocr import EasyOCRTextExtractor
from app.models.ocr_schema import OCRResult, OCRStatus

__all__ = [
	"ImageEncodingResult",
	"ImageEncodingStatus",
	"EasyOCRTextExtractor",
	"OCRResult",
	"OCRStatus",
	"OpenCLIPImageEncoder",
	"SentenceTransformerTextEncoder",
	"TextEncodingResult",
	"TextEncodingStatus",
	"TranscriptionResult",
	"TranscriptionStatus",
	"WhisperTranscriber",
	"resolve_device",
]
