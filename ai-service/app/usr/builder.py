"""USR construction from modality-specific foundation outputs."""

from typing import Optional
from uuid import UUID

from app.usr.models import (
    USRAudioTranscript,
    USRImage,
    USRModality,
    USROCR,
    USRText,
    USRVideo,
    UnifiedSemanticRepresentation,
)


class UnifiedSemanticRepresentationBuilder:
    """Build USR without making predictions or invoking CMREF."""

    def build(
        self,
        request_id: UUID,
        text: Optional[USRText] = None,
        image: Optional[USRImage] = None,
        ocr: Optional[USROCR] = None,
        audio: Optional[USRAudioTranscript] = None,
        video: Optional[USRVideo] = None,
        modality_metadata: Optional[dict] = None,
        embedding_metadata: Optional[dict] = None,
        preprocessing_metadata: Optional[dict] = None,
    ) -> UnifiedSemanticRepresentation:
        available = []
        if text is not None:
            available.append(USRModality.TEXT)
        if image is not None:
            available.append(USRModality.IMAGE)
        if ocr is not None:
            available.append(USRModality.OCR)
        if audio is not None:
            available.append(USRModality.AUDIO_TRANSCRIPT)
        if video is not None:
            if video.transcript or video.transcript_segments:
                available.append(USRModality.VIDEO_TRANSCRIPT)
            if video.frame_paths or video.frame_embeddings:
                available.append(USRModality.VIDEO_FRAMES)

        if not available:
            raise ValueError("USR requires at least one modality representation")

        return UnifiedSemanticRepresentation(
            request_id=request_id,
            available_modalities=available,
            text=text,
            image=image,
            ocr=ocr,
            audio=audio,
            video=video,
            modality_metadata=modality_metadata or {},
            embedding_metadata=embedding_metadata or {},
            preprocessing_metadata=preprocessing_metadata or {},
        )
