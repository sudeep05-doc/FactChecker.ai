# Proposed CMREF Technical Specification

**Status:** Design only. No CMREF implementation is included in this document's
change.

**Scope:** Cross-Modal Reasoning Framework (CMREF) between the implemented
Unified Semantic Representation (USR) boundary and the future Reasoning
Representation (RR) and CMREA layers.

CMREF is the proposed research architecture for combining available modality
representations, measuring their relationships, and producing an auditable
reasoning score. The equations below are a design proposal, not a claimed
novel method and not an experimental result. The foundation models that create
representations remain replaceable open-source components; CMREF does not claim
novelty for them.

## 1. Design Goals

CMREF must:

- accept any non-empty subset of the modalities available in USR;
- remain model-agnostic at the USR boundary;
- distinguish missing evidence from negative evidence;
- make fusion, alignment, consistency, contradiction, context, and decision
  evidence inspectable;
- avoid treating source reputation or an OCR/encoder confidence as truth;
- avoid producing a fake-news label by itself;
- operate on a small number of modality representations on local hardware.

CMREF emits structured evidence for RR and CMREA. The final user-facing label,
confidence calibration, and explanation policy are outside this design.

## 2. USR Input Boundary

Let the set of possible USR modalities be:

\[
\mathcal{M}\_{all} = \{T, I, O, A, V_T, V_F\}
\]

where:

- \(T\): cleaned text representation;
- \(I\): image representation, usually an OpenCLIP embedding;
- \(O\): OCR text and detection information;
- \(A\): audio transcript and timestamped segments;
- \(V_T\): video transcript and timestamped segments;
- \(V_F\): sampled video-frame representations.

For a request, USR supplies an available subset:

\[
\mathcal{M} \subseteq \mathcal{M}\_{all}, \qquad |\mathcal{M}| \geq 1
\]

The current USR contract represents audio and video transcripts as transcript
objects and video frames as frame paths or frame embeddings. A modality may be
present while its embedding is not yet available. CMREF therefore forms a
second set:

\[
\mathcal{E} = \{m \in \mathcal{M} : m \text{ has a valid finite embedding}\}
\]

Textual outputs such as OCR and transcripts can later be embedded by the text
encoder before CMREF. Until then they remain available as structured evidence
and are not silently treated as vectors.

For every \(m \in \mathcal{E}\), define the input embedding and metadata as:

\[
h_m \in \mathbb{R}^{d_m}, \quad
\text{model}\_m, \quad d_m, \quad n_m \in \{0,1\}
\]

where \(n_m\) records whether the upstream representation is already
normalized. The implemented USR layer checks that \(d_m\) equals the number of
values and that every value is finite.

Non-embedding data remains attached to the modality record:

\[
q_m = \text{modality metadata}, \qquad
p_m = \text{preprocessing metadata}
\]

These fields may contain dimensions, extraction status, timestamps, language,
OCR boxes, or model timing. They are evidence about processing, not evidence
that a claim is true.

## 3. Dimension Alignment and Normalization

Different foundation models can produce different dimensions. CMREF must not
concatenate incompatible vectors. A versioned projection adapter is therefore
associated with each embedding model:

\[
P_m : \mathbb{R}^{d_m} \rightarrow \mathbb{R}^{d}
\]

where \(d\) is the configured CMREF working dimension. If \(d_m=d\) and the
representation is already in the agreed space, \(P_m\) may be the identity.
Otherwise \(P_m\) must be explicitly configured and versioned. CMREF must fail
with a configuration error when a required adapter is absent; it must not
silently truncate or pad vectors.

The aligned vector is L2-normalized with an epsilon for numerical stability:

\[
\tilde{z}\_m = P_m h_m
\]

\[
z_m = \frac{\tilde{z}\_m}
{\max(\lVert \tilde{z}\_m \rVert_2, \varepsilon)}
\]

with \(\varepsilon > 0\), for example \(10^{-12}\). A zero-norm vector is
invalid evidence for similarity calculations and should be marked unusable,
not converted into an arbitrary direction.

The normalized vector is accompanied by an evidence weight:

\[
w_m = w^{base}\_m \cdot w^{quality}\_m \cdot w^{freshness}\_m
\]

The default weight for a present, valid modality is 1.0. Missing modalities
receive no weight and are not assigned a zero-quality interpretation. Any
non-default weighting function must be versioned and recorded in RR.

## 4. Pairwise Cross-Modal Alignment

For every unordered pair of available embedded modalities,
\((i,j) \in \mathcal{P}(\mathcal{E})\), compute cosine alignment:

\[
s\_{ij} = z_i^\top z_j
\]

Because vectors are normalized, \(s\_{ij} \in [-1,1]\). For easier reporting,
map it to a bounded alignment value:

\[
a*{ij} = \frac{s*{ij}+1}{2} \in [0,1]
\]

The pair record must retain both \(s*{ij}\) and \(a*{ij}\), the modality names,
model names, and the projection version. The pairwise score is semantic
alignment evidence only. High alignment does not prove that the underlying
claim is true, and low alignment does not by itself prove misinformation.

A weighted overall alignment is:

\[
A = \frac{\sum*{(i,j)\in\mathcal{P}(\mathcal{E})}
w_i w_j a*{ij}}
{\sum\_{(i,j)\in\mathcal{P}(\mathcal{E})} w_i w_j}
\]

when the denominator is positive. If fewer than two valid embeddings exist,
\(A\) is **undefined**, not zero.

## 5. Consistency Analysis

Consistency evaluates whether the available embedded modalities support a
coherent shared representation. The base consistency value is the weighted
pairwise alignment:

\[
C\_{align} = A
\]

A future contextual consistency term may incorporate structured information
such as timestamps, extracted entities, or page/frame correspondence:

\[
C*{context} =
\frac{\sum*{m\in\mathcal{E}} w*m c_m}
{\sum*{m\in\mathcal{E}} w_m}
\]

where \(c_m \in [0,1]\) is produced by a separately versioned contextual
relation component. If contextual evidence is unavailable, it is omitted rather
than assigned a fabricated score.

For configured coefficients \(\lambda_a,\lambda_c \geq 0\), with available
terms renormalized to sum to one:

\[
C = \lambda*a C*{align} + \lambda*c C*{context}
\]

If no consistency term is computable, CMREF records `consistency: null` and
sets a reason such as `INSUFFICIENT_CROSS_MODAL_EVIDENCE`.

## 6. Contradiction Detection

Cosine dissimilarity is not sufficient to claim contradiction. A contradiction
signal must come from an explicit relation evaluator operating on compatible
content, such as a later NLI-style text relation module or a configured
cross-modal relation function.

For each eligible pair, let:

\[
d*{ij} = g*{contra}(r_i,r_j,q_i,q_j) \in [0,1]
\]

where \(r*i,r_j\) are semantic or textual relation inputs and \(g*{contra}\)
returns the strength of a contradiction relation. The evaluator must also
return a validity flag; unavailable relations are omitted.

The aggregate contradiction signal is:

\[
D = \frac{\sum*{(i,j)\in\mathcal{P}\_D} w_i w_j d*{ij}}
{\sum\_{(i,j)\in\mathcal{P}\_D} w_i w_j}
\]

where \(\mathcal{P}\_D\) is the set of pairs for which contradiction evidence
exists. If \(\mathcal{P}\_D\) is empty, \(D\) is undefined. It must not be set
to zero, because no test is not the same as no contradiction.

For a lightweight initial implementation, a clearly labeled alignment-based
proxy may be used only as a diagnostic:

\[
D*{proxy,ij} = \max(0,\tau_c-s*{ij})
\]

This proxy must be labeled `alignment_proxy`, must not be described as semantic
contradiction, and must not be used as a standalone fake-news decision.

## 7. Semantic Feature Fusion

The fused representation is a weighted barycenter of aligned vectors:

\[
z*{fuse} =
\frac{\sum*{m\in\mathcal{E}} w*m z_m}
{\max(\sum*{m\in\mathcal{E}} w_m,\varepsilon)}
\]

The fused vector is normalized once more:

\[
z^\*_{fuse} =
\frac{z_{fuse}}
{\max(\lVert z\_{fuse}\rVert_2,\varepsilon)}
\]

CMREF records the contributing modality weights and the list of omitted
modalities. If only one embedded modality is present, the fused representation
is that modality and pairwise alignment remains undefined.

## 8. Contextual Reasoning

Contextual reasoning combines non-embedding evidence without treating it as a
truth oracle. Let \(x_k \in [0,1]\) be a bounded, versioned contextual feature,
such as:

- temporal agreement between transcript and sampled frame metadata;
- entity overlap between text, OCR, transcript, and captions;
- URL/article extraction completeness;
- source or acquisition metadata completeness, without domain reputation;
- whether a modality was independently acquired or merely duplicated.

With non-negative coefficients \(\gamma_k\) normalized over available
features:

\[
X = \sum*{k\in\mathcal{K}*{available}} \gamma_k x_k
\]

If a feature is not available, it is removed from the denominator and recorded
as missing. No missing feature receives an implicit negative value.

## 9. Reasoning Score and Decision Evidence

CMREF combines the available evidence into a bounded reasoning score. Let
\(\hat{C}, \hat{D}, \hat{X}\) denote only defined values, and let their weights
be renormalized over the defined terms:

\[
R = \sum*{k\in\{C,1-D,X\}*{defined}} \alpha_k k,
\qquad \alpha_k \geq 0,
\qquad \sum_k\alpha_k=1
\]

Here \(1-D\) means absence of contradiction evidence, not proof of truth. If
no reasoning evidence is defined, \(R\) is undefined.

A configurable decision-evidence score can then be represented as:

\[
S\_{evidence} =
\sigma\left(
b + \beta_R R + \beta_A A - \beta_D D + \beta_X X
\right)
\]

where:

\[
\sigma(u)=\frac{1}{1+e^{-u}}
\]

and all coefficients are configuration/calibration artifacts, not claims of
novelty. The sign and interpretation of this score must be explicitly named
(for example, `support_coherence_score` or `misinformation_evidence_score`).
CMREF itself must not silently map it to `LIKELY_FAKE` or `LIKELY_REAL`; that
mapping belongs to the later decision/calibration layer and must be supported by
experiments.

To avoid false precision, CMREF should return `null` for undefined scores and a
structured list of reasons. CMREA can later turn the available terms, weights,
and relation paths into a human-readable explanation.

## 10. Proposed Algorithm

```text
CMREF(usr, configuration):
    validate usr.request_id and available modality consistency
    active <- modalities declared in usr.available_modalities
    embedded <- active modalities with finite, dimension-checked embeddings

    for each modality m in embedded:
        adapter <- configuration.projection_adapter(m.embedding.model_name)
        if adapter is missing and dimensions are incompatible:
            record configuration error and omit m from computable fusion
        else:
            z[m] <- L2_normalize(adapter(m.embedding.values), epsilon)
            w[m] <- configured quality weight, recorded in reasoning trace

    if embedded vectors exist:
        for each unordered pair (i, j) in embedded:
            alignment[i, j] <- cosine(z[i], z[j])
            record both signed cosine and [0, 1] alignment
        fused <- normalized weighted barycenter of z[m]
    else:
        fused <- undefined

    compute consistency from defined alignment/context terms
    compute contradiction only from valid relation-evaluator outputs
    compute contextual features that are present
    compute reasoning score from defined terms with renormalized weights
    compute decision evidence only if configured and calibrated inputs exist

    return RR containing:
        fused representation reference
        modality contributions
        pairwise alignment records
        consistency and contradiction records
        context records
        score definitions and undefined-score reasons
        projection/model/configuration versions
```

## 11. Data Flow

```text
CAL and preprocessing outputs
        |
        v
Foundation model outputs
(text, image, OCR, transcript, frame features)
        |
        v
USR
(request ID, optional modalities, embeddings, metadata)
        |
        v
CMREF input validation
        |
        +--> projection and normalization
        +--> pairwise alignment
        +--> consistency analysis
        +--> contradiction relation evaluation
        +--> contextual reasoning
        +--> weighted feature fusion
        |
        v
RR
(structured traces, scores, omissions, undefined reasons)
        |
        v
CMREA
(confidence, contribution, reasoning path, explanation)
```

No CMREF stage reads MongoDB or calls the React frontend. No CMREF stage
changes the public verification contract in this design-only task.

## 12. Missing Modality Handling

Missing modalities are normal. For a request with only text, CMREF can produce
an aligned text representation but cannot compute pairwise cross-modal
alignment. For text plus image, one pair is available. For text, OCR, and video
frames, CMREF computes only the pairs whose representations are valid.

Rules:

1. Missing modality: omit it and record it as unavailable.
2. Present but failed preprocessing: retain the failure in the trace; do not
   turn it into a negative semantic signal.
3. Present transcript without embedding: retain transcript evidence, but exclude
   it from vector fusion until an embedding is available.
4. Present embedding with incompatible dimension and no adapter: exclude it
   from fusion and return a configuration error.
5. Fewer than two embedded modalities: pairwise scores and alignment-based
   consistency are undefined.
6. No valid embedded modality: fusion is undefined, but structured text/OCR/
   transcript evidence may remain available for a later component.

## 13. Edge Cases

- **Empty USR:** reject before CMREF; the current USR builder requires at least
  one representation.
- **Zero vector:** reject from normalization or mark invalid; never divide by
  zero or invent a direction.
- **NaN or infinity:** reject at the USR boundary and again before numerical
  operations.
- **Duplicate modality:** reject duplicate entries in `available_modalities`.
- **Duplicate content:** record duplicate/derived-source metadata and avoid
  treating duplicate copies as independent evidence.
- **Conflicting timestamps:** retain the conflict as contextual evidence and
  do not silently align events.
- **OCR with no detections:** preserve the OCR result with no text; do not
  manufacture a contradiction.
- **Video with no sampled frames:** mark frame evidence unavailable while
  retaining any transcript.
- **Contradiction unavailable:** set the contradiction score to null rather
  than zero.
- **Extreme pair scores:** clip only at documented numerical boundaries after
  validation; retain the original signed cosine for auditability.

## 14. Numerical Stability and Reproducibility

- Validate every embedding value with `isfinite` before computation.
- Use float32 or float64 consistently within one CMREF run.
- Normalize with `max(norm, epsilon)` and reject zero-norm vectors.
- Clamp cosine results to `[-1, 1]` before converting to alignment values to
  absorb small floating-point drift.
- Compute weighted denominators with a positive-epsilon check.
- Use a stable sigmoid implementation for large positive or negative logits.
- Record model names, checkpoint versions, projection versions, coefficients,
  epsilon, and device in RR.
- Keep deterministic preprocessing and fixed modality ordering for reproducible
  traces.
- Do not infer confidence from a raw cosine score; confidence calibration is a
  CMREA/pipeline concern.

## 15. Computational Complexity

Let \(k=|\mathcal{E}|\) be the number of modalities with compatible embeddings
and \(d\) the common embedding dimension.

- Projection and normalization: \(O(kd)\) for linear adapters, excluding the
  cost of the foundation models.
- Pairwise alignment: \(O(k^2d)\) time and \(O(k^2)\) pair-record storage.
- Weighted fusion: \(O(kd)\) time and \(O(d)\) working memory.
- Context and contradiction evaluators: implementation-dependent; they must
  expose their own bounded cost and avoid loading duplicate media.

The current planned modality set has at most six entries, so pairwise reasoning
is small. CMREF should stream or summarize large metadata and should not retain
full audio/video contents when only embeddings, transcripts, or sampled-frame
references are required.

## 16. Implementation Boundary

The future CMREF implementation should consume
`UnifiedSemanticRepresentation` and emit a structured RR object. It should not
reach into React, Node.js, MongoDB, or foundation-model download code. Model
adapters, relation evaluators, score coefficients, and calibration versions
should be injected configuration so the CMREF design remains model-agnostic and
testable.

This document defines the proposed architecture only. It does not claim that
the equations are novel, does not report performance, and does not implement
CMREF, RR orchestration, CMREA, or a truth/fake decision.
