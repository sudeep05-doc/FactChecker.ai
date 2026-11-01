"""Strongly typed Reasoning Representation (RR) audit structures."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RRModel(BaseModel):
	model_config = ConfigDict(extra="forbid")


class RRProjectionAdapter(RRModel):
	modality: str
	model_name: str
	source_dimension: int = Field(ge=1)
	target_dimension: int = Field(ge=1)
	version: str
	weight_version: str


class RRNormalizedRepresentationReference(RRModel):
	modality: str
	reference: str
	dimension: int = Field(ge=1)
	model_name: str
	projection_version: str
	value_count: int = Field(ge=1)


class RRAlignmentRecord(RRModel):
	left_modality: str
	right_modality: str
	left_model: str
	right_model: str
	projection_version: str
	left_weight: float = Field(ge=0)
	right_weight: float = Field(ge=0)
	signed_cosine: float = Field(ge=-1, le=1)
	bounded_alignment: float = Field(ge=0, le=1)
	diagnostic_proxy: Optional[float] = None
	diagnostic_proxy_label: Optional[str] = None


class RRSimilarityRecord(RRModel):
	left_modality: str
	right_modality: str
	left_model: str
	right_model: str
	projection_version: str
	cosine_similarity: float = Field(ge=-1, le=1)


class RRConsistencyStatus(str, Enum):
	AVAILABLE = "available"
	UNAVAILABLE = "unavailable"
	NOT_RUN = "not_run"
	FAILED = "failed"
	NOT_VALIDATED = "not_validated"


class RRConsistencyRecord(RRModel):
	alignment: Optional[float] = Field(
		default=None,
		ge=0,
		le=1,
		description="Deprecated compatibility field; must remain null because cosine alignment is not consistency.",
	)
	contextual: Optional[float] = Field(
		default=None,
		ge=0,
		le=1,
		description="Deprecated compatibility field; raw contextual features are stored separately.",
	)
	score: Optional[float] = Field(
		default=None,
		ge=0,
		le=1,
		description="Consistency measurement emitted only by a defined evaluator.",
	)
	status: RRConsistencyStatus = RRConsistencyStatus.UNAVAILABLE
	evaluator_version: Optional[str] = None
	unavailable_reason: Optional[str] = "CONSISTENCY_EVALUATOR_UNAVAILABLE"
	weights: Dict[str, float] = Field(default_factory=dict)

	@model_validator(mode="after")
	def validate_consistency_contract(self) -> "RRConsistencyRecord":
		if self.alignment is not None or self.contextual is not None:
			raise ValueError(
				"consistency alignment/contextual fields are deprecated; "
				"store raw measurements in their own records"
			)
		if self.status == RRConsistencyStatus.AVAILABLE:
			if self.score is None or not self.evaluator_version:
				raise ValueError(
					"available consistency requires a score and evaluator version"
				)
			if self.unavailable_reason is not None:
				raise ValueError("available consistency cannot have an unavailable reason")
		else:
			if self.score is not None:
				raise ValueError("consistency score requires an available evaluator")
			if not self.unavailable_reason:
				raise ValueError("unavailable consistency requires an explicit reason")
			if self.weights:
				raise ValueError("consistency weights require an available evaluator")
		return self


class RRContradictionRecord(RRModel):
	left_modality: str
	right_modality: str
	left_weight: float = Field(ge=0)
	right_weight: float = Field(ge=0)
	contradiction_score: float = Field(ge=0, le=1)
	relation_metadata: Dict[str, Any] = Field(default_factory=dict)


class RRContextualFeatureRecord(RRModel):
	name: str
	value: float = Field(ge=0, le=1)
	version: str
	metadata: Dict[str, Any] = Field(default_factory=dict)


class RRConfigurationError(RRModel):
	code: str
	message: str
	modality: Optional[str] = None


class RRDiagnosticProxy(RRModel):
	label: str
	records: List[Dict[str, Any]] = Field(default_factory=list)


class RRNumericalStability(RRModel):
	epsilon: float = Field(gt=0)
	cosine_clamped: bool


class ReasoningRepresentation(RRModel):
	"""Audit artifact passed from CMREF toward CMREA."""

	request_id: UUID
	timestamp: datetime
	available_modalities: List[str] = Field(default_factory=list)
	omitted_modalities: List[str] = Field(default_factory=list)
	modality_weights: Dict[str, float] = Field(default_factory=dict)
	projection_adapters: List[RRProjectionAdapter] = Field(default_factory=list)
	model_versions: Dict[str, str] = Field(default_factory=dict)
	normalized_representation_references: List[RRNormalizedRepresentationReference] = Field(default_factory=list)
	pairwise_alignments: List[RRAlignmentRecord] = Field(default_factory=list)
	pairwise_similarities: List[RRSimilarityRecord] = Field(default_factory=list)
	consistency: RRConsistencyRecord
	contradiction: Optional[float] = Field(default=None, ge=0, le=1)
	contradiction_records: List[RRContradictionRecord] = Field(default_factory=list)
	contextual_features: List[RRContextualFeatureRecord] = Field(default_factory=list)
	fused_representation_reference: Optional[str] = None
	fusion_metadata: Dict[str, Any] = Field(default_factory=dict)
	reasoning_score: Optional[float] = Field(default=None, ge=0, le=1)
	decision_evidence: Optional[float] = Field(default=None, ge=0, le=1)
	undefined_score_reasons: List[str] = Field(default_factory=list)
	configuration_errors: List[RRConfigurationError] = Field(default_factory=list)
	numerical_stability: RRNumericalStability
	diagnostic_proxies: List[RRDiagnosticProxy] = Field(default_factory=list)
