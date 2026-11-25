"""Event analytics service with mandatory sample sizes and data coverage indicators.

Never fabricates averages from empty datasets: every numeric metric returns None
when response_count == 0, paired with an explicit `data_coverage` object.
"""

from typing import Any
from uuid import UUID

import numpy as np
import pandas as pd
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import (
    ActionCategory,
    ActionStatus,
    AttendanceStatus,
    ConnectionType,
    EvidenceClassification,
    FollowUpStatus,
    OutcomeType,
    ScoreStatus,
)
from app.core.exceptions import NotFoundError
from app.models.impact import (
    FollowUpSchedule,
    FollowUpSubmission,
    ImpactOutcome,
    ParticipantAction,
    ProfessionalConnection,
)
from app.models.participant import AttendanceRecord, Event, EventRegistration
from app.models.questionnaire import AssessmentSubmission
from app.models.scoring import (
    MeasurementPillar,
    ParticipantDimensionScore,
    ParticipantImpactScore,
)


def _coverage_indicator(numerator: int, denominator: int) -> dict[str, Any]:
    if denominator <= 0 or numerator <= 0:
        ratio = 0.0
    else:
        ratio = round(min(1.0, numerator / denominator), 4)

    if numerator == 0 or denominator == 0:
        level = "none"
    elif ratio < 0.30:
        level = "low"
    elif ratio < 0.70:
        level = "moderate"
    else:
        level = "high"

    return {
        "response_count": numerator,
        "reference_population": denominator,
        "coverage_ratio": ratio,
        "coverage_level": level,
    }


def _numeric_stats(values: list[float], denominator: int) -> dict[str, Any]:
    count = len(values)
    coverage = _coverage_indicator(count, denominator)
    if count == 0:
        return {
            "average": None,
            "median": None,
            "std_dev": None,
            "min": None,
            "max": None,
            "response_count": 0,
            "data_coverage": coverage,
        }
    arr = np.asarray(values, dtype=float)
    return {
        "average": round(float(np.mean(arr)), 2),
        "median": round(float(np.median(arr)), 2),
        "std_dev": round(float(np.std(arr, ddof=1)), 2) if count > 1 else 0.0,
        "min": round(float(np.min(arr)), 2),
        "max": round(float(np.max(arr)), 2),
        "response_count": count,
        "data_coverage": coverage,
    }


class AnalyticsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _require_event(self, event_id: UUID) -> Event:
        event = self.db.get(Event, event_id)
        if event is None:
            raise NotFoundError("Event", event_id)
        return event

    def _event_population_counts(self, event_id: UUID) -> dict[str, int]:
        registered = int(
            self.db.execute(
                select(func.count(EventRegistration.id)).where(
                    EventRegistration.event_id == event_id
                )
            ).scalar_one()
        )
        attendance_total_records = int(
            self.db.execute(
                select(func.count(AttendanceRecord.id)).where(
                    AttendanceRecord.event_id == event_id
                )
            ).scalar_one()
        )
        confirmed_attendees = int(
            self.db.execute(
                select(func.count(AttendanceRecord.id)).where(
                    AttendanceRecord.event_id == event_id,
                    AttendanceRecord.attendance_status.in_(
                        [AttendanceStatus.CONFIRMED.value, AttendanceStatus.PARTIAL.value]
                    ),
                )
            ).scalar_one()
        )
        unique_assessment_respondents = int(
            self.db.execute(
                select(func.count(distinct(AssessmentSubmission.participant_id))).where(
                    AssessmentSubmission.event_id == event_id
                )
            ).scalar_one()
        )
        return {
            "registered": registered,
            "attendance_total_records": attendance_total_records,
            "confirmed_attendees": confirmed_attendees,
            "unique_assessment_respondents": unique_assessment_respondents,
        }

    def get_event_overview(self, event_id: UUID) -> dict[str, Any]:
        event = self._require_event(event_id)
        counts = self._event_population_counts(event_id)
        registered = counts["registered"]
        confirmed = counts["confirmed_attendees"]
        att_records = counts["attendance_total_records"]
        respondents = counts["unique_assessment_respondents"]

        # Reliable attendance rate only when registered > 0 AND attendance records exist
        attendance_rate = (
            round(confirmed / registered, 4)
            if registered > 0 and att_records > 0
            else None
        )
        reference_pop = confirmed if confirmed > 0 else registered
        assessment_completion_rate = (
            round(respondents / reference_pop, 4) if reference_pop > 0 else None
        )

        latest_scores = list(
            self.db.execute(
                select(ParticipantImpactScore).where(
                    ParticipantImpactScore.event_id == event_id,
                    ParticipantImpactScore.is_latest.is_(True),
                )
            )
            .scalars()
            .all()
        )

        overall_vals = [
            s.overall_impact_score
            for s in latest_scores
            if s.overall_impact_score is not None
        ]
        immediate_vals = [
            s.immediate_impact_score
            for s in latest_scores
            if s.immediate_impact_score is not None
        ]
        application_vals = [
            s.post_event_application_score
            for s in latest_scores
            if s.post_event_application_score is not None
        ]
        sustained_vals = [
            s.sustained_impact_score
            for s in latest_scores
            if s.sustained_impact_score is not None
        ]

        outcomes = list(
            self.db.execute(
                select(ImpactOutcome).where(ImpactOutcome.event_id == event_id)
            )
            .scalars()
            .all()
        )
        outcomes_by_evidence = {
            ev.value: sum(1 for o in outcomes if o.evidence_classification == ev.value)
            for ev in EvidenceClassification
        }

        actions = list(
            self.db.execute(
                select(ParticipantAction).where(ParticipantAction.event_id == event_id)
            )
            .scalars()
            .all()
        )

        schedules = list(
            self.db.execute(
                select(FollowUpSchedule).where(FollowUpSchedule.event_id == event_id)
            )
            .scalars()
            .all()
        )
        fu_completed = sum(
            1 for s in schedules if s.status == FollowUpStatus.COMPLETED.value
        )

        score_denom = max(reference_pop, len(latest_scores))

        return {
            "event_id": str(event.id),
            "event_slug": event.slug,
            "event_title": event.title,
            "event_date": event.event_date.isoformat(),
            "participation": {
                "total_registered_participants": registered,
                "total_confirmed_attendees": confirmed,
                "attendance_records_available": att_records,
                "attendance_rate": attendance_rate,
                "attendance_data_reliable": att_records > 0 and registered > 0,
                "assessment_respondents_count": respondents,
                "assessment_completion_rate": assessment_completion_rate,
                "assessment_data_coverage": _coverage_indicator(respondents, reference_pop),
            },
            "impact_scores": {
                "overall_event_impact": _numeric_stats(overall_vals, score_denom),
                "immediate_event_impact": _numeric_stats(immediate_vals, score_denom),
                "post_event_application_impact": _numeric_stats(application_vals, score_denom),
                "sustained_longitudinal_impact": _numeric_stats(sustained_vals, score_denom),
                "score_status_breakdown": {
                    st.value: sum(1 for s in latest_scores if s.status == st.value)
                    for st in (
                        ScoreStatus.CALCULATED,
                        ScoreStatus.PARTIAL,
                        ScoreStatus.INSUFFICIENT_DATA,
                    )
                },
            },
            "actions_progress": {
                "total_actions": len(actions),
                "by_status": {
                    st.value: sum(1 for a in actions if a.action_status == st.value)
                    for st in ActionStatus
                },
            },
            "outcomes_summary": {
                "total_outcomes": len(outcomes),
                "by_evidence_classification": outcomes_by_evidence,
            },
            "follow_up_summary": {
                "total_scheduled": len(schedules),
                "total_completed": fu_completed,
                "completion_rate": round(fu_completed / len(schedules), 4)
                if schedules
                else None,
                "data_coverage": _coverage_indicator(fu_completed, len(schedules)),
            },
        }

    def get_pillar_analytics(self, event_id: UUID) -> dict[str, Any]:
        event = self._require_event(event_id)
        counts = self._event_population_counts(event_id)
        reference_pop = (
            counts["confirmed_attendees"]
            if counts["confirmed_attendees"] > 0
            else counts["registered"]
        )

        pillars = list(
            self.db.execute(
                select(MeasurementPillar)
                .where(MeasurementPillar.is_active.is_(True))
                .order_by(MeasurementPillar.display_order.asc())
            )
            .scalars()
            .all()
        )

        latest_score_ids = list(
            self.db.execute(
                select(ParticipantImpactScore.id).where(
                    ParticipantImpactScore.event_id == event_id,
                    ParticipantImpactScore.is_latest.is_(True),
                )
            )
            .scalars()
            .all()
        )

        dim_rows: list[ParticipantDimensionScore] = []
        if latest_score_ids:
            dim_rows = list(
                self.db.execute(
                    select(ParticipantDimensionScore).where(
                        ParticipantDimensionScore.impact_score_id.in_(latest_score_ids)
                    )
                )
                .scalars()
                .all()
            )

        denom = max(reference_pop, len(latest_score_ids))
        pillar_results = []
        for p in pillars:
            p_rows = [r for r in dim_rows if r.pillar_id == p.id]
            valid_vals = [
                r.normalised_score
                for r in p_rows
                if r.status == ScoreStatus.CALCULATED.value and r.normalised_score is not None
            ]
            missing_count = sum(1 for r in p_rows if r.status != ScoreStatus.CALCULATED.value)
            stats = _numeric_stats(valid_vals, denom)
            pillar_results.append(
                {
                    "pillar_id": str(p.id),
                    "pillar_code": p.code,
                    "pillar_name": p.name,
                    "impact_category": p.impact_category,
                    "default_weight": p.default_weight,
                    "missing_count": missing_count,
                    **stats,
                }
            )

        return {
            "event_id": str(event.id),
            "event_title": event.title,
            "participants_scored": len(latest_score_ids),
            "pillars": pillar_results,
        }

    def get_networking_analytics(self, event_id: UUID) -> dict[str, Any]:
        event = self._require_event(event_id)
        counts = self._event_population_counts(event_id)
        reference_pop = (
            counts["confirmed_attendees"]
            if counts["confirmed_attendees"] > 0
            else counts["registered"]
        )

        connections = list(
            self.db.execute(
                select(ProfessionalConnection).where(
                    ProfessionalConnection.event_id == event_id
                )
            )
            .scalars()
            .all()
        )

        unique_participants = len({c.participant_id for c in connections})
        per_participant_counts: list[float] = []
        if connections:
            df = pd.DataFrame(
                [{"participant_id": str(c.participant_id)} for c in connections]
            )
            per_participant_counts = [
                float(x) for x in df.groupby("participant_id").size().tolist()
            ]

        return {
            "event_id": str(event.id),
            "event_title": event.title,
            "total_connections_reported": len(connections),
            "participants_reporting_connections": unique_participants,
            "connections_per_reporting_participant": _numeric_stats(
                per_participant_counts, max(reference_pop, unique_participants)
            ),
            "follow_up_conversations_count": sum(
                1 for c in connections if c.follow_up_occurred
            ),
            "collaborations_started_count": sum(
                1 for c in connections if c.collaboration_started
            ),
            "opportunities_discovered_count": sum(
                1 for c in connections if c.opportunity_discovered
            ),
            "by_connection_type": {
                ct.value: sum(1 for c in connections if c.connection_type == ct.value)
                for ct in ConnectionType
            },
            "by_evidence_classification": {
                ev.value: sum(
                    1 for c in connections if c.evidence_classification == ev.value
                )
                for ev in EvidenceClassification
            },
            "data_coverage": _coverage_indicator(unique_participants, reference_pop),
        }

    def get_application_analytics(self, event_id: UUID) -> dict[str, Any]:
        event = self._require_event(event_id)
        counts = self._event_population_counts(event_id)
        reference_pop = (
            counts["confirmed_attendees"]
            if counts["confirmed_attendees"] > 0
            else counts["registered"]
        )

        actions = list(
            self.db.execute(
                select(ParticipantAction).where(ParticipantAction.event_id == event_id)
            )
            .scalars()
            .all()
        )
        outcomes = list(
            self.db.execute(
                select(ImpactOutcome).where(ImpactOutcome.event_id == event_id)
            )
            .scalars()
            .all()
        )

        intended_count = sum(
            1 for a in actions if a.action_status == ActionStatus.INTENDED.value
        )
        in_progress_count = sum(
            1 for a in actions if a.action_status == ActionStatus.IN_PROGRESS.value
        )
        completed_count = sum(
            1 for a in actions if a.action_status == ActionStatus.COMPLETED.value
        )
        abandoned_count = sum(
            1 for a in actions if a.action_status == ActionStatus.ABANDONED.value
        )

        action_participants = len({a.participant_id for a in actions})
        completing_participants = len(
            {a.participant_id for a in actions if a.action_status == ActionStatus.COMPLETED.value}
        )

        return {
            "event_id": str(event.id),
            "event_title": event.title,
            "actions": {
                "total_recorded": len(actions),
                "intended_only_count": intended_count,
                "in_progress_count": in_progress_count,
                "completed_count": completed_count,
                "abandoned_count": abandoned_count,
                "implementation_conversion_rate": round(
                    completed_count / len(actions), 4
                )
                if actions
                else None,
                "participants_with_actions": action_participants,
                "participants_with_completed_actions": completing_participants,
                "by_category": {
                    cat.value: sum(1 for a in actions if a.action_category == cat.value)
                    for cat in ActionCategory
                },
                "data_coverage": _coverage_indicator(action_participants, reference_pop),
            },
            "outcomes": {
                "total_outcomes": len(outcomes),
                "by_type": {
                    ot.value: sum(1 for o in outcomes if o.outcome_type == ot.value)
                    for ot in OutcomeType
                },
                "by_evidence_classification": {
                    ev.value: sum(
                        1 for o in outcomes if o.evidence_classification == ev.value
                    )
                    for ev in EvidenceClassification
                },
                "verified_outcome_ratio": round(
                    sum(
                        1
                        for o in outcomes
                        if o.evidence_classification == EvidenceClassification.VERIFIED.value
                    )
                    / len(outcomes),
                    4,
                )
                if outcomes
                else None,
            },
        }

    def get_follow_up_analytics(self, event_id: UUID) -> dict[str, Any]:
        event = self._require_event(event_id)

        schedules = list(
            self.db.execute(
                select(FollowUpSchedule)
                .options(selectinload(FollowUpSchedule.submissions))
                .where(FollowUpSchedule.event_id == event_id)
                .order_by(FollowUpSchedule.due_date.asc())
            )
            .scalars()
            .all()
        )

        stage_order: list[str] = []
        grouped: dict[str, list[FollowUpSchedule]] = {}
        for sched in schedules:
            if sched.follow_up_stage not in grouped:
                stage_order.append(sched.follow_up_stage)
                grouped[sched.follow_up_stage] = []
            grouped[sched.follow_up_stage].append(sched)

        stages_comparison = []
        for stage_code in stage_order:
            stage_scheds = grouped[stage_code]
            total_scheduled = len(stage_scheds)
            completed = [
                s for s in stage_scheds if s.status == FollowUpStatus.COMPLETED.value
            ]
            pending = [
                s
                for s in stage_scheds
                if s.status in {FollowUpStatus.PENDING.value, FollowUpStatus.SCHEDULED.value}
            ]
            overdue = [s for s in stage_scheds if s.status == FollowUpStatus.OVERDUE.value]
            submissions = [sub for s in stage_scheds for sub in s.submissions]

            # Calculate average positive response ratio for boolean follow-up questions
            positive_ratios: list[float] = []
            total_reported_actions = 0
            for sub in submissions:
                total_reported_actions += len(sub.reported_actions_json or [])
                bools = [
                    v for v in (sub.responses_json or {}).values() if isinstance(v, bool)
                ]
                if bools:
                    positive_ratios.append(
                        round((sum(1 for b in bools if b) / len(bools)) * 100.0, 2)
                    )

            stages_comparison.append(
                {
                    "follow_up_stage": stage_code,
                    "scheduled_count": total_scheduled,
                    "completed_count": len(completed),
                    "pending_count": len(pending),
                    "overdue_count": len(overdue),
                    "completion_rate": round(len(completed) / total_scheduled, 4)
                    if total_scheduled > 0
                    else None,
                    "submissions_count": len(submissions),
                    "reported_actions_count": total_reported_actions,
                    "positive_action_signal": _numeric_stats(
                        positive_ratios, total_scheduled
                    ),
                    "by_evidence_classification": {
                        ev.value: sum(
                            1
                            for sub in submissions
                            if sub.evidence_classification == ev.value
                        )
                        for ev in EvidenceClassification
                    },
                    "data_coverage": _coverage_indicator(len(completed), total_scheduled),
                }
            )

        return {
            "event_id": str(event.id),
            "event_title": event.title,
            "stages_tracked": len(stages_comparison),
            "stages": stages_comparison,
        }
