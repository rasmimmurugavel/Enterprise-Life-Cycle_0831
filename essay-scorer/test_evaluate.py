from pathlib import Path

from evaluate import evaluate_essay

REFERENCE = Path(__file__).parent / "reference"


def test_strong_essay_scores_higher_than_weak_essay():
    strong = evaluate_essay(REFERENCE / "strong-essay.docx")
    weak = evaluate_essay(REFERENCE / "weak-essay.docx")
    assert strong["total"] > weak["total"]


def test_missing_evidence_scores_one_and_says_not_enough_text():
    weak = evaluate_essay(REFERENCE / "weak-essay.docx")
    assert weak["evidence"]["score"] == 1
    assert weak["evidence"]["evidence"] == "not enough text"


def test_every_score_has_evidence():
    for essay in ("strong-essay.docx", "weak-essay.docx"):
        results = evaluate_essay(REFERENCE / essay)
        for key in ("structure", "evidence", "vocabulary_range"):
            assert results[key]["evidence"]
