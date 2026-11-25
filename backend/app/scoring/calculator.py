"""Pure, deterministic scoring engine calculator for the six CCI STEM Connect pillars."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.core.enums import (
    ActionStatus,
    EvidenceClassification,
    ImpactCategory,
    ScoreStatus,
    ScoringRuleType,
)
from app.models.impact import FollowUpSubmission, ImpactOutcome, ParticipantAction
from app.models.questionnaire import AssessmentResponse, Question
from app.models.scoring import ScoringDimension, ScoringFramework, ScoringRule

EVIDENCE_MULTIPLIERS = {
    EvidenceClassification.SELF_REPORTED.value: 0.75,
    EvidenceClassification.DOCUMENTED.value: 0.90,
    EvidenceClassification.VERIFIED.value: 1.00,
}


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def evaluate_rule(
    rule: ScoringRule,
    question: Question,
    response: AssessmentResponse,
) -> float | None:
    """Evaluate a single response against a ScoringRule into a 0–100 score.

    Returns None if the response is empty/missing or if the question is non-scorable.
    """
    if not question.is_scorable or not rule.is_active:
        return None

    cfg = rule.rule_config or {}
    rtype = rule.rule_type

    if rtype == ScoringRuleType.RATING_SCALE.value:
        if response.response_numeric is None:
            return None
        min_v = float(cfg.get("min", 1.0))
        max_v = float(cfg.get("max", 5.0))
        if max_v <= min_v:
            return None
        return round(_clamp(((response.response_numeric - min_v) / (max_v - min_v)) * 100.0), 4)

    if rtype == ScoringRuleType.YES_NO.value:
        if response.response_boolean is None:
            return None
        yes_score = float(cfg.get("yes_score", 100.0))
        no_score = float(cfg.get("no_score", 0.0))
        return round(_clamp(yes_score if response.response_boolean else no_score), 4)

    if rtype == ScoringRuleType.SINGLE_CHOICE.value:
        val = response.response_text
        if val is None:
            return None
        option_scores: dict[str, Any] = cfg.get("option_scores") or {}
        if val in option_scores:
            score_raw = float(option_scores[val])
        else:
            opt_match = next(
                (o for o in question.options if o.option_value == val and o.score_value is not None),
                None,
            )
            if opt_match is None or opt_match.score_value is None:
                return None
            score_raw = float(opt_match.score_value)
        max_score = float(cfg.get("max_score", 100.0))
        if max_score <= 0:
            return None
        return round(_clamp((score_raw / max_score) * 100.0), 4)

    if rtype == ScoringRuleType.MULTIPLE_CHOICE.value:
        vals = response.response_json
        if not isinstance(vals, list) or len(vals) == 0:
            return None
        option_scores = cfg.get("option_scores") or {}
        opt_lookup = {
            o.option_value: float(o.score_value)
            for o in question.options
            if o.score_value is not None
        }
        scores = []
        for v in vals:
            if v in option_scores:
                scores.append(float(option_scores[v]))
            elif v in opt_lookup:
                scores.append(opt_lookup[v])
        if not scores:
            return None
        mode = cfg.get("aggregation", "sum")
        max_score = float(cfg.get("max_score", 100.0))
        if max_score <= 0:
            return None
        agg = sum(scores) if mode == "sum" else (sum(scores) / len(scores))
        return round(_clamp((agg / max_score) * 100.0), 4)

    if rtype == ScoringRuleType.NUMERIC_THRESHOLD.value:
        if response.response_numeric is None:
            return None
        val = float(response.response_numeric)
        brackets = cfg.get("brackets")
        if isinstance(brackets, list) and brackets:
            # Sort brackets descending by min threshold
            sorted_brackets = sorted(brackets, key=lambda b: float(b["min"]), reverse=True)
            for b in sorted_brackets:
                if val >= float(b["min"]):
                    return round(_clamp(float(b["score"])), 4)
            return 0.0
        min_v = float(cfg.get("min_value", 0.0))
        target_v = float(cfg.get("target_value", 5.0))
        if target_v <= min_v:
            return None
        return round(_clamp(((val - min_v) / (target_v - min_v)) * 100.0), 4)

    if rtype == ScoringRuleType.VALUE_MAP.value:
        mapping: dict[str, Any] = cfg.get("map") or {}
        key = (
            response.response_text
            if response.response_text is not None
            else (str(response.response_numeric) if response.response_numeric is not None else None)
        )
        if key is None or key not in mapping:
            return None
        return round(_clamp(float(mapping[key])), 4)

    return None


@dataclass
class ComputedDimension:
    dimension_id: UUID
    pillar_id: UUID
    pillar_code: str
    pillar_name: str
    impact_category: str
    configured_weight: float
    effective_weight: float | None
    raw_score: float | None
    normalised_score: float | None
    questions_answered: int
    questions_total: int
    completeness_ratio: float
    status: str


@dataclass
class ComputedImpactScore:
    status: str
    overall_impact_score: float | None
    immediate_impact_score: float | None
    post_event_application_score: float | None
    sustained_impact_score: float | None
    completeness_ratio: float
    covered_pillars_count: int
    total_pillars_count: int
    weight_renormalised: bool
    dimensions: list[ComputedDimension] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def compute_sustained_impact(
    *,
    follow_up_submissions: list[FollowUpSubmission],
    actions: list[ParticipantAction],
    outcomes: list[ImpactOutcome],
) -> tuple[float | None, dict[str, Any]]:
    """Calculate sustained longitudinal impact strictly from post-event follow-ups,
    completed actions (never intentions), and evidence-weighted outcomes.

    Returns (None, metadata) when no follow-up or completed sustained evidence exists.
    """
    completed_actions = [a for a in actions if a.action_status == ActionStatus.COMPLETED.value]
    intended_actions = [a for a in actions if a.action_status == ActionStatus.INTENDED.value]
    in_progress_actions = [a for a in actions if a.action_status == ActionStatus.IN_PROGRESS.value]

    if not follow_up_submissions and not completed_actions and not outcomes:
        return None, {
            "follow_up_stages_completed": [],
            "completed_actions_count": 0,
            "intended_actions_count": len(intended_actions),
            "in_progress_actions_count": len(in_progress_actions),
            "outcomes_count": 0,
            "note": "No longitudinal follow-up or completed action evidence yet.",
        }

    component_scores: list[tuple[float, float]] = []  # (score, weight)

    # 1. Follow-up stage progression & boolean/numeric follow-up answers
    stages_completed = sorted({fs.follow_up_stage for fs in follow_up_submissions})
    if follow_up_submissions:
        fu_item_scores: list[float] = []
        for fs in follow_up_submissions:
            ev_mult = EVIDENCE_MULTIPLIERS.get(fs.evidence_classification, 0.75)
            # Score explicit boolean / numeric items inside responses_json
            bool_vals = [v for v in (fs.responses_json or {}).values() if isinstance(v, bool)]
            num_vals = [
                float(v)
                for v in (fs.responses_json or {}).values()
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            ]
            stage_signals: list[float] = []
            if bool_vals:
                stage_signals.append((sum(1 for b in bool_vals if b) / len(bool_vals)) * 100.0)
            if num_vals:
                # Normalise 1-5 Likert ratings inside follow-up responses
                normalised_nums = [_clamp(((n - 1.0) / 4.0) * 100.0) if 1.0 <= n <= 5.0 else _clamp(n) for n in num_vals]
                stage_signals.append(sum(normalised_nums) / len(normalised_nums))
            if stage_signals:
                fu_item_scores.append((sum(stage_signals) / len(stage_signals)) * ev_mult)
            else:
                fu_item_scores.append(50.0 * ev_mult)
        if fu_item_scores:
            component_scores.append((sum(fu_item_scores) / len(fu_item_scores), 0.45))

    # 2. Completed actions ratio (intentions are tracked separately and NEVER award completion score)
    total_tracked_actions = len(completed_actions) + len(in_progress_actions) + len(intended_actions)
    if completed_actions:
        completion_rate_score = (len(completed_actions) / max(1, total_tracked_actions)) * 100.0
        avg_ev = sum(
            EVIDENCE_MULTIPLIERS.get(a.evidence_classification, 0.75)
            for a in completed_actions
        ) / len(completed_actions)
        component_scores.append((_clamp(completion_rate_score * avg_ev), 0.30))

    # 3. Outcomes weighted by evidence classification (self_reported < documented < verified)
    if outcomes:
        outcome_scores = [
            100.0 * EVIDENCE_MULTIPLIERS.get(o.evidence_classification, 0.75)
            for o in outcomes
        ]
        component_scores.append((sum(outcome_scores) / len(outcome_scores), 0.25))

    if not component_scores:
        return None, {
            "follow_up_stages_completed": stages_completed,
            "completed_actions_count": len(completed_actions),
            "intended_actions_count": len(intended_actions),
            "in_progress_actions_count": len(in_progress_actions),
            "outcomes_count": len(outcomes),
        }

    total_w = sum(w for _, w in component_scores)
    sustained_score = round(sum(s * (w / total_w) for s, w in component_scores), 2)
    return sustained_score, {
        "follow_up_stages_completed": stages_completed,
        "completed_actions_count": len(completed_actions),
        "intended_actions_count": len(intended_actions),
        "in_progress_actions_count": len(in_progress_actions),
        "outcomes_count": len(outcomes),
        "outcomes_by_evidence": {
            ev.value: sum(1 for o in outcomes if o.evidence_classification == ev.value)
            for ev in EvidenceClassification
        },
    }


def calculate_impact_score(
    *,
    framework: ScoringFramework,
    dimensions: list[ScoringDimension],
    rules: list[ScoringRule],
    responses_by_question_id: dict[UUID, AssessmentResponse],
    questions_by_id: dict[UUID, Question],
    follow_up_submissions: list[FollowUpSubmission] | None = None,
    actions: list[ParticipantAction] | None = None,
    outcomes: list[ImpactOutcome] | None = None,
) -> ComputedImpactScore:
    """Compute pillar-level and composite impact scores with automatic missing-dimension
    exclusion and weight renormalisation.
    """
    rules_by_dim: dict[UUID, list[ScoringRule]] = {}
    for rule in rules:
        if rule.is_active:
            rules_by_dim.setdefault(rule.dimension_id, []).append(rule)

    computed_dims: list[ComputedDimension] = []
    total_scorable_questions = 0
    total_answered_scorable = 0

    for dim in dimensions:
        dim_rules = rules_by_dim.get(dim.id, [])
        q_total = len(dim_rules)
        total_scorable_questions += q_total

        weighted_scores: list[tuple[float, float]] = []
        for rule in dim_rules:
            resp = responses_by_question_id.get(rule.question_id)
            question = questions_by_id.get(rule.question_id)
            if resp is None or question is None:
                continue
            q_score = evaluate_rule(rule, question, resp)
            if q_score is not None:
                weighted_scores.append((q_score, rule.question_weight))

        q_answered = len(weighted_scores)
        total_answered_scorable += q_answered
        dim_completeness = round(q_answered / q_total, 4) if q_total > 0 else 0.0
        min_req = max(framework.min_questions_per_pillar, dim.min_questions_required)

        if q_answered >= min_req and q_answered > 0:
            w_sum = sum(w for _, w in weighted_scores)
            raw = sum(s * w for s, w in weighted_scores) / w_sum
            normalised = round(_clamp(raw), 2)
            dim_status = ScoreStatus.CALCULATED.value
        else:
            raw = None
            normalised = None
            dim_status = ScoreStatus.MISSING.value

        computed_dims.append(
            ComputedDimension(
                dimension_id=dim.id,
                pillar_id=dim.pillar_id,
                pillar_code=dim.pillar.code,
                pillar_name=dim.pillar.name,
                impact_category=dim.impact_category,
                configured_weight=dim.weight,
                effective_weight=None,
                raw_score=round(raw, 4) if raw is not None else None,
                normalised_score=normalised,
                questions_answered=q_answered,
                questions_total=q_total,
                completeness_ratio=dim_completeness,
                status=dim_status,
            )
        )

    available_dims = [d for d in computed_dims if d.status == ScoreStatus.CALCULATED.value]
    covered_count = len(available_dims)
    total_pillars = len(computed_dims)
    overall_completeness = (
        round(total_answered_scorable / total_scorable_questions, 4)
        if total_scorable_questions > 0
        else 0.0
    )

    # Calculate sustained impact separately regardless of immediate completeness
    sustained_score, sustained_meta = compute_sustained_impact(
        follow_up_submissions=follow_up_submissions or [],
        actions=actions or [],
        outcomes=outcomes or [],
    )

    # Insufficient data guard (Scenario C)
    if (
        covered_count < framework.min_pillars_required
        or overall_completeness < framework.min_completeness_ratio
        or covered_count == 0
    ):
        return ComputedImpactScore(
            status=ScoreStatus.INSUFFICIENT_DATA.value,
            overall_impact_score=None,
            immediate_impact_score=None,
            post_event_application_score=next(
                (
                    d.normalised_score
                    for d in available_dims
                    if d.impact_category == ImpactCategory.APPLICATION.value
                ),
                None,
            ),
            sustained_impact_score=sustained_score,
            completeness_ratio=overall_completeness,
            covered_pillars_count=covered_count,
            total_pillars_count=total_pillars,
            weight_renormalised=False,
            dimensions=computed_dims,
            metadata={
                "reason": "Insufficient scorable assessment data to calculate composite impact score.",
                "min_pillars_required": framework.min_pillars_required,
                "min_completeness_ratio": framework.min_completeness_ratio,
                "total_scorable_questions": total_scorable_questions,
                "answered_scorable_questions": total_answered_scorable,
                "excluded_pillars": [
                    d.pillar_code for d in computed_dims if d.status != ScoreStatus.CALCULATED.value
                ],
                "sustained_impact_details": sustained_meta,
            },
        )

    # Renormalise available weights (Scenario A & B)
    available_weight_sum = sum(d.configured_weight for d in available_dims)
    weight_renormalised = covered_count < total_pillars
    for d in available_dims:
        d.effective_weight = round(d.configured_weight / available_weight_sum, 6)

    overall_score = round(
        sum(
            (d.normalised_score or 0.0) * (d.configured_weight / available_weight_sum)
            for d in available_dims
        ),
        2,
    )

    # Immediate Event Impact (strictly immediate pillars — never confused with post-event application)
    immediate_dims = [
        d for d in available_dims if d.impact_category == ImpactCategory.IMMEDIATE.value
    ]
    if immediate_dims:
        imm_w_sum = sum(d.configured_weight for d in immediate_dims)
        immediate_score = round(
            sum((d.normalised_score or 0.0) * (d.configured_weight / imm_w_sum) for d in immediate_dims),
            2,
        )
    else:
        immediate_score = None

    # Post-Event Application Impact (strictly application pillar)
    app_dims = [
        d for d in available_dims if d.impact_category == ImpactCategory.APPLICATION.value
    ]
    if app_dims:
        app_w_sum = sum(d.configured_weight for d in app_dims)
        application_score = round(
            sum((d.normalised_score or 0.0) * (d.configured_weight / app_w_sum) for d in app_dims),
            2,
        )
    else:
        application_score = None

    overall_status = (
        ScoreStatus.PARTIAL.value if weight_renormalised else ScoreStatus.CALCULATED.value
    )

    return ComputedImpactScore(
        status=overall_status,
        overall_impact_score=overall_score,
        immediate_impact_score=immediate_score,
        post_event_application_score=application_score,
        sustained_impact_score=sustained_score,
        completeness_ratio=overall_completeness,
        covered_pillars_count=covered_count,
        total_pillars_count=total_pillars,
        weight_renormalised=weight_renormalised,
        dimensions=computed_dims,
        metadata={
            "total_scorable_questions": total_scorable_questions,
            "answered_scorable_questions": total_answered_scorable,
            "available_weight_sum_before_renorm": round(available_weight_sum, 4),
            "excluded_pillars": [
                d.pillar_code for d in computed_dims if d.status != ScoreStatus.CALCULATED.value
            ],
            "sustained_impact_details": sustained_meta,
        },
    )
