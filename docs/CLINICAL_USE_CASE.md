# Pratibmb Clinical

> **A privacy-first behavioral history tool for licensed mental health clinicians.**
> Status: Proposal / Pre-development. Not yet a clinical product.

---

## The problem

Therapy depends almost entirely on patient self-report, which has well-documented limitations:

- **Recency bias** — patients only recall the last 1–2 weeks
- **Mood-congruent memory** — depressed patients selectively retrieve negative events
- **Defense mechanisms** — repression, denial, intellectualization filter what's spoken
- **Social desirability** — patients perform for the therapist
- **Limited self-insight** — most behavioral patterns are invisible to the person living them
- **Time scarcity** — 50-minute sessions can't reconstruct a 5-year history

Clinicians know this. They develop heuristics, ask careful questions, and infer patterns over many sessions. But there is a **massive untapped data source** sitting on every patient's phone: their actual digital communication history.

A patient's 5–10 year message archive (WhatsApp, iMessage, etc.) is **objective behavioral data**:

- Sleep patterns inferred from message timestamps
- Attachment patterns from how they communicate with romantic partners vs. parents vs. friends
- Emotional trajectory across years
- Major life events with linguistic signatures around them
- Topic clusters showing values, preoccupations, avoidances
- Communication style shifts that may correlate with episodes

No existing clinical tool surfaces this data. Mood-tracking apps (Daylio, Bearable) capture only prospective subjective data. AI therapy chatbots (Woebot, Wysa) don't analyze patient history. EHRs store therapist notes, not patient behavioral data.

## Why Pratibmb is uniquely suited

The consumer Pratibmb already solves the hardest technical and regulatory problems for a clinical product:

| Clinical requirement | Pratibmb already has |
|---|---|
| **HIPAA-friendly architecture** | 100% local processing — no cloud transmission |
| **Patient data sovereignty** | All data stays on patient's device |
| **Auditable for IRB/institutions** | Open source (AGPL-3.0) |
| **Multi-platform import** | 8 platforms supported (WhatsApp, iMessage, Facebook, Instagram, Telegram, Gmail, Discord, X) |
| **Longitudinal view** | Year-by-year slider already in UI |
| **Profile extraction** | Already extracts relationships, life events, communication style |
| **Cross-platform desktop** | Works on macOS, Windows, Linux — fits any clinical workflow |

The clinical product is **mostly about adding a different lens** on the same data, plus a structured export for the therapist.

## Proposed clinical features

These are **information-surfacing tools for the clinician**, not diagnostic tools. The clinician interprets. The tool informs.

### 1. Sentiment & affect timeline

- Daily/weekly sentiment scores plotted across years
- Annotated with major life events
- Visual identification of episodic patterns (recurrent low periods, hypomanic phases, anniversary reactions)

### 2. Communication pattern analysis

- **Message volume by time of day** — sleep disruption indicators
- **Response latency** — withdrawal periods, hyperarousal
- **Message length variance** — racing thoughts vs. anhedonia
- **Punctuation/capitalization shifts** — distress signals
- Based on validated linguistic markers (LIWC-style: pronouns, time orientation, negation, emotional valence)

### 3. Relational mapping

- **Attachment style indicators** drawn from communication with romantic partners
- **Social network density** changes over time (isolation indicators)
- **Conflict patterns** — escalation, withdrawal, repair sequences
- **Differential communication style** — clinical vs. casual code-switching by relationship

### 4. Crisis & risk language detection

- Surface (never alert on) statistically-significant shifts toward:
  - Hopelessness language ("no point", "can't go on", "tired of...")
  - Constricted future orientation
  - Burdensomeness themes
- **Always paired with:** safety disclaimer, "this is not a clinical assessment", recommendation to discuss with patient
- Critical: NEVER auto-alert authorities. Therapist's judgment only.

### 5. Therapy session prep brief

- Single-page exportable brief: "What's happened in your patient's life since the last session"
- Auto-generated topic suggestions based on recent emotional content
- Privacy filter: clinician chooses what categories to surface

### 6. Patient-controlled consent layer

- Patient explicitly grants access per category, per time range
- Some content (e.g. messages with named third parties) can be excluded
- Patient can revoke at any time
- No data ever leaves the patient's device — therapist views via screen-share or patient-controlled export

## Ethical boundaries (non-negotiable)

This product cannot be built without these guardrails:

1. **Not diagnostic.** Surfaces patterns. Never claims pathology. Output language is descriptive, not prescriptive.
2. **Patient consent is granular and revocable.** Per category, per relationship, per time range.
3. **Third-party messages.** Counterparty consent is impossible to verify — the tool must blur/aggregate third-party contributions, not display verbatim.
4. **No cloud transmission, ever.** Local-first is a clinical safety feature, not a marketing claim.
5. **Crisis detection has known false-positive and false-negative rates.** Tool flags for *clinician review*, never for automated escalation.
6. **No insurance/employer integration.** Behavioral data must never reach payers or employers.
7. **Open-source and auditable.** Published methodology, replicable analyses.
8. **Clinical validation before clinical claims.** No "clinically validated" language until peer-reviewed studies exist.

## Market opportunity

- ~700,000 licensed mental health professionals in the US (psychologists, LCSWs, LMFTs, psychiatrists)
- Average willingness to pay for clinical SaaS: $50–200/month
- Adjacent products: SimplePractice ($69/mo, 200K+ users), TheraNest, TherapyNotes
- **Strong differentiator:** No competitor offers patient behavioral history analysis at all

## Go-to-market sequence

**Phase 0 (now — months 0–3):**
- Capture clinician interest via consumer site
- Publish this positioning document
- 10–20 informal interviews with practicing therapists to validate hypotheses

**Phase 1 (months 3–6):**
- Build sentiment + communication pattern modules
- Pilot with 5–10 therapists in private beta
- Develop session prep brief format

**Phase 2 (months 6–12):**
- Add relational mapping + risk language modules
- Partner with academic clinical psychology program for validation study
- Apply for IRB review at one academic institution

**Phase 3 (months 12+):**
- Publish validation paper
- Launch to general clinical market
- Pursue HIPAA Business Associate Agreement compliance certification

## Pricing (hypothetical)

| Tier | Price | Patients |
|---|---|---|
| Solo practitioner | $79/mo | up to 30 active patients |
| Small practice | $199/mo | up to 100 active patients |
| Institutional | Custom | Unlimited, with audit logs and SSO |

## Why this could work

The combination of:
- **Existing privacy-first architecture** (the hardest part is done)
- **Genuine clinical utility** (no competitor surfaces this data)
- **Open source + AGPL** (clinical institutions trust this)
- **Therapists' real frustrations with self-report limitations** (the demand exists)

…makes this a credible vertical extension. Not a pivot. The consumer Pratibmb stays the consumer Pratibmb. Pratibmb Clinical is a separate product, separately positioned, separately priced.

## Risks

- **Regulatory complexity** — health data is heavily regulated even when local
- **Liability** — if a patient harms themselves and the tool "missed" risk signals, lawsuit risk exists
- **Slow B2B clinical sales** — 6–12 month sales cycles are normal
- **Validation requirement** — clinical claims need peer-reviewed evidence, which takes 1–2 years
- **Therapist tech adoption** — historically slow; UX must be clinician-friendly, not engineer-friendly

## Next steps

1. **Validate demand**: 10 therapist interviews. If 5+ are interested, proceed.
2. **Add to consumer site**: a "For Clinicians" section that captures interested clinician emails — costs nothing, signals demand.
3. **Build Phase 1 modules**: sentiment timeline + session prep brief. ~4 weeks of work.
4. **Identify academic partner**: one psychology program willing to co-design validation.

---

*This document describes a proposed clinical product. It is not a current Pratibmb feature. It does not constitute a clinical claim. Pratibmb is not a medical device.*
