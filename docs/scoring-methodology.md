# Scoring Methodology — CCI STEM Connect Impact Engine

## 1. Six Measurement Pillars (Framework v1.0)

| Pillar | Code | Proposed Weight | Impact Horizon |
|---|---|---:|---|
| Professional Engagement | `professional_engagement` | 15% | Immediate |
| Knowledge and Insights | `knowledge_and_insights` | 20% | Immediate |
| Workplace Excellence | `workplace_excellence` | 15% | Immediate |
| Recognition and Rewards | `recognition_and_rewards` | 15% | Immediate |
| Networking and Relationships | `networking_and_relationships` | 20% | Immediate |
| Post-Event Application | `post_event_application` | 15% | Post-Event Application |
| **Total** | | **100%** | |

All weights, thresholds, and question rules are database-configurable through `/api/v1/scoring/frameworks`.

## 2. Qualitative vs. Scorable Separation

Only questions explicitly marked `is_scorable = true` AND linked via an active `scoring_rules` entry contribute to numerical scores. Reflective question cards (such as *"What can you teach someone in 10 minutes?"*) are stored as qualitative data and never receive synthetic numerical scores.

## 3. Question-Level Normalisation (`0–100`)

- **Rating Scale**: `((value - min) / (max - min)) * 100`, clamped to `[0, 100]`.
- **Yes / No**: Configurable `yes_score` (default `100`) and `no_score` (default `0`).
- **Single Choice**: Selected option `score_value` scaled against `max_score` into `[0, 100]`.
- **Multiple Choice**: Sum or mean of selected option scores scaled against `max_score`, clamped to `[0, 100]`.
- **Numeric Threshold**: Linear interpolation from `min_value` to `target_value` or step brackets mapped into `[0, 100]`.

## 4. Missing Data Exclusion & Weight Renormalisation

- If a pillar has fewer answered scorable questions than `min_questions_per_pillar`, that pillar is marked `status = "missing"` and **excluded** — never treated as `0`.
- When $k < 6$ pillars are available (e.g., 4 of 6 completed), the remaining configured weights $w_i$ are renormalised so they sum to `1.0`:
  $$w'_i = \frac{w_i}{\sum_{j \in A} w_j}, \qquad \text{Overall Impact Score} = \sum_{i \in A} w'_i \cdot s_i$$
- If covered pillars $< \text{min\_pillars\_required}$ (default `2`) or scorable completeness $< \text{min\_completeness\_ratio}$ (default `0.25`), the composite score is marked `status = "insufficient_data"` with `overall_impact_score = null`.

## 5. Horizon Separation & Evidence Classification

The engine strictly separates three horizons so immediate enthusiasm never implies long-term workplace impact:

1. **Immediate Event Impact**: Renormalised average across immediate pillars only.
2. **Post-Event Application**: Derived strictly from actual application responses (never from `intended` actions).
3. **Sustained Longitudinal Impact**: Derived strictly from completed 30/60/90-day follow-up submissions, completed actions, and evidence-weighted outcomes (`self_reported`: 0.75, `documented`: 0.90, `verified`: 1.00). Returns `null` when no longitudinal follow-up or completed action evidence exists.
