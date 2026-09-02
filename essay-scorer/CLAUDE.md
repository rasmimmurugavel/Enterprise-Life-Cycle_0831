# CLAUDE.md — Essay Scorer

Rules that must not break:
1. Deterministic only: fixed rules/regex, no AI calls, no randomness.
2. Never guess — insufficient text scores 1 and is labeled "not enough text".
3. Score only from literal signals: paragraph breaks, quote marks, the fixed phrase list, and word counts. Never judge argument quality, opinions, or factual accuracy.
4. Total = Structure + Evidence + Vocabulary Range, out of 15 (see scoped-problem.docx for thresholds).
5. Every printed score carries the excerpt or statistic it came from.

Commands:
- Run: `python evaluate.py <file.pdf or .docx>`
- Test: `python -m pytest test_evaluate.py`
