"""
Sentiment & affect timeline (skeleton — not implemented).

Goal: produce a daily/weekly sentiment trajectory from the user's outgoing
messages, so a clinician can visualize emotional patterns across years.

PROPOSED APPROACH

1. For each outgoing message, compute a sentiment score using a small
   local model. Candidates:
   - VADER (rule-based, fast, English) — good baseline, no model download
   - DistilBERT-SST2 quantized — better, requires ~250MB model
   - Reuse Gemma-3-4B with a structured-output prompt — already loaded
2. Aggregate into daily/weekly buckets with confidence intervals.
3. Identify statistically-significant inflection points (e.g. CUSUM change
   detection) — surface as "potential events worth discussing."
4. Cross-reference with the existing LifeEvent extraction to annotate the
   timeline with known events.

OUTPUT SHAPE (proposed)

    SentimentTimeline(
        daily=[(date, mean_score, n_messages, ci_low, ci_high), ...],
        weekly=[(week_start, mean_score, n_messages, ci_low, ci_high), ...],
        inflection_points=[(date, magnitude, direction, surrounding_topics)],
        annotations=[(date, event_summary, source="profile.life_events")],
    )

CLINICAL CAVEATS to surface in any UI/export

- Sentiment scores from text are noisy. Sarcasm, in-jokes, and shorthand all
  fool models. Treat as a hypothesis-generator, not evidence.
- Outgoing messages only — incoming messages reflect counterparties.
- Volume effects: low-message-count days have wide confidence intervals.
- Cultural/linguistic variation in emotional expression is not accounted for.
- A flat sentiment line does NOT mean the patient is fine. Anhedonia and
  affective flattening can present as low-variance neutral text.
"""
from __future__ import annotations

# Implementation deferred — see docs/CLINICAL_USE_CASE.md for roadmap.


def compute_sentiment_timeline(*args, **kwargs):
    raise NotImplementedError(
        "Sentiment timeline analysis is not yet implemented. "
        "See docs/CLINICAL_USE_CASE.md for the proposed clinical extension."
    )
