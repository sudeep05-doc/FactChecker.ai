"""Named, configuration-driven baseline and ablation experiments."""

from app.evaluation.schemas import AblationComponent, EvaluationConfiguration


BASELINE_CONFIGURATIONS = {
    "text_only": EvaluationConfiguration(name="text_only", modalities=["text"]),
    "image_only": EvaluationConfiguration(name="image_only", modalities=["image"]),
    "text_image": EvaluationConfiguration(name="text_image", modalities=["text", "image"]),
    "text_image_ocr": EvaluationConfiguration(name="text_image_ocr", modalities=["text", "image", "ocr"]),
    "all_available": EvaluationConfiguration(name="all_available", modalities=["text", "image", "ocr", "audio", "video"]),
}

ABLATION_CONFIGURATIONS = {
    "baseline_text": EvaluationConfiguration(name="baseline_text", modalities=["text"]),
    "baseline_image": EvaluationConfiguration(name="baseline_image", modalities=["image"]),
    "multimodal_no_alignment": EvaluationConfiguration(
        name="multimodal_no_alignment", modalities=["text", "image"],
        enabled_components=[AblationComponent.CONSISTENCY, AblationComponent.DECISION_CALIBRATION],
    ),
    "multimodal_alignment": EvaluationConfiguration(
        name="multimodal_alignment", modalities=["text", "image"],
        enabled_components=[AblationComponent.ALIGNMENT, AblationComponent.DECISION_CALIBRATION],
    ),
    "multimodal_alignment_consistency": EvaluationConfiguration(
        name="multimodal_alignment_consistency", modalities=["text", "image"],
        enabled_components=[AblationComponent.ALIGNMENT, AblationComponent.CONSISTENCY, AblationComponent.DECISION_CALIBRATION],
    ),
    "multimodal_full_reasoning": EvaluationConfiguration(
        name="multimodal_full_reasoning", modalities=["text", "image", "ocr"],
        enabled_components=list(AblationComponent),
    ),
}


def get_configuration(name: str) -> EvaluationConfiguration:
    try:
        return (BASELINE_CONFIGURATIONS | ABLATION_CONFIGURATIONS)[name].model_copy(deep=True)
    except KeyError as error:
        raise ValueError(f"unknown evaluation configuration: {name}") from error
