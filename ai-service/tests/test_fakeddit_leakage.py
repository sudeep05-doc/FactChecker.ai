import pytest

from app.evaluation.fakeddit_leakage import assign_components, connected_components


def _record(sample_id: str, image_hash: str, label: str, *, quarantined: bool = False) -> dict:
    return {
        "sample_id": sample_id,
        "image_sha256": image_hash,
        "canonical_label": label,
        "quarantined": quarantined,
    }


def test_exact_image_hashes_form_connected_components() -> None:
    records = [
        _record("train-a", "same-bytes", "FAKE"),
        _record("test-a", "same-bytes", "FAKE"),
        _record("independent", "other-bytes", "REAL"),
    ]

    groups = connected_components(records)

    assert {frozenset(group) for group in groups} == {
        frozenset({"train-a", "test-a"}),
        frozenset({"independent"}),
    }


def test_unreviewed_near_candidates_are_not_grouped_implicitly() -> None:
    records = [_record("near-a", "sha-a", "FAKE"), _record("near-b", "sha-b", "REAL")]

    assert len(connected_components(records)) == 2
    assert connected_components(records, near_pairs=(("near-a", "near-b"),)) == [["near-a", "near-b"]]


def test_quarantined_confirmed_pair_is_excluded_and_exact_group_stays_together() -> None:
    records = [
        _record("same-1", "duplicate", "FAKE"),
        _record("same-2", "duplicate", "FAKE"),
        _record("conflict-fake", "near-fake", "FAKE", quarantined=True),
        _record("conflict-real", "near-real", "REAL", quarantined=True),
        _record("single-fake", "fake-only", "FAKE"),
        _record("single-real", "real-only", "REAL"),
    ]

    assigned, groups, targets = assign_components(
        records,
        seed=42,
        near_pairs=(("conflict-fake", "conflict-real"),),
    )

    assert "conflict-fake" not in assigned
    assert "conflict-real" not in assigned
    assert assigned["same-1"] == assigned["same-2"]
    assert set(assigned) == {"same-1", "same-2", "single-fake", "single-real"}
    assert sum(targets["FAKE"].values()) == 3
    assert sum(targets["REAL"].values()) == 1
    assert all(
        len({assigned[sample_id] for sample_id in group if sample_id in assigned}) <= 1
        for group in groups
    )


def test_assignment_is_deterministic_even_if_input_order_changes() -> None:
    records = [
        _record(f"sample-{index}", f"sha-{index}", "FAKE" if index % 2 else "REAL")
        for index in range(40)
    ]

    first, _, _ = assign_components(records, seed=19)
    second, _, _ = assign_components(list(reversed(records)), seed=19)

    assert first == second


def test_partial_component_quarantine_is_rejected() -> None:
    records = [
        _record("keep", "same-sha", "FAKE"),
        _record("drop", "same-sha", "FAKE", quarantined=True),
    ]

    with pytest.raises(ValueError, match="complete confirmed component"):
        assign_components(records)


def test_duplicate_sample_ids_are_rejected() -> None:
    records = [
        _record("duplicate", "sha-a", "FAKE"),
        _record("duplicate", "sha-b", "REAL"),
    ]

    with pytest.raises(ValueError, match="duplicate sample IDs"):
        connected_components(records)