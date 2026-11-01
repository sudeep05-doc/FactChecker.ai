"""Preprocessing layer orchestration."""

from typing import Optional

from app.cal.schemas import CALResult
from app.preprocessing.image import ImagePreprocessor
from app.preprocessing.image_schema import ImagePreprocessingResult
from app.preprocessing.pdf import PDFPreprocessor
from app.preprocessing.pdf_schema import PDFPreprocessingResult
from app.preprocessing.schemas import TextPreprocessingResult
from app.preprocessing.text import TextPreprocessor
from app.preprocessing.audio import AudioPreprocessor
from app.preprocessing.audio_schema import AudioPreprocessingResult
from app.preprocessing.video import VideoPreprocessor
from app.preprocessing.video_schema import VideoPreprocessingResult


class PreprocessingService:
    """Route normalized CAL text into the deterministic text preprocessor."""

    def __init__(
        self,
        text_preprocessor: Optional[TextPreprocessor] = None,
        image_preprocessor: Optional[ImagePreprocessor] = None,
        pdf_preprocessor: Optional[PDFPreprocessor] = None,
        audio_preprocessor: Optional[AudioPreprocessor] = None,
        video_preprocessor: Optional[VideoPreprocessor] = None,
    ) -> None:
        self.text_preprocessor = text_preprocessor or TextPreprocessor()
        self.image_preprocessor = image_preprocessor or ImagePreprocessor()
        self.pdf_preprocessor = pdf_preprocessor or PDFPreprocessor()
        self.audio_preprocessor = audio_preprocessor or AudioPreprocessor()
        self.video_preprocessor = video_preprocessor or VideoPreprocessor()

    def process(self, content: CALResult):
        if content.input_type == "image":
            return self.image_preprocessor.process(content)
        if content.input_type == "pdf":
            return self.pdf_preprocessor.process(content)
        if content.input_type == "audio":
            return self.audio_preprocessor.process(content)
        if content.input_type == "video":
            return self.video_preprocessor.process(content)
        return self.text_preprocessor.process(content)
