"""
Pratibmb Clinical — proposed extension for licensed mental health clinicians.

This module is **early-stage scaffolding**, not a clinical product. None of the
analyses here are validated for clinical use. Pratibmb is not a medical device.

The intent is to surface objective behavioral patterns from a patient's own
messaging history (timestamps, sentiment, communication patterns, language
shifts over time) for clinician review — never for automated diagnosis,
risk scoring, or third-party alerting.

See docs/CLINICAL_USE_CASE.md for the full positioning document.

PRINCIPLES (non-negotiable for any code added here):

1. Information-surfacing only. No diagnostic claims. No DSM/ICD-style labels.
2. All data stays local. Same architecture as consumer Pratibmb.
3. Patient consent is granular and revocable. Per category, per relationship,
   per time range. Default-deny.
4. Third-party messages (counterparties who didn't consent) must be aggregated
   or blurred — never displayed verbatim in clinical exports.
5. Risk language detection (when implemented) flags patterns for **clinician
   review** only. Never auto-escalates. Never contacts third parties.
6. No insurance, employer, or payer integration. Ever.
7. Clinical claims require peer-reviewed validation. Until then: descriptive
   language only, with explicit "not a clinical assessment" disclaimers.
"""

__all__ = [
    "sentiment",
    "patterns",
    "session_brief",
]
