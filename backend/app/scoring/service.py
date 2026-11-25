"""Scoring framework management and score calculation orchestration service."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.core.enums import ScoreScope, ScoreStatus
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.security import ActorContext
from app.models.impact import FollowUpSubmission, ImpactOutcome, ParticipantAction
from app.models.participant import EventRegistration
from app.models.questionnaire import (
    AssessmentResponse,
    AssessmentSubmission,
    Question,
    QuestionnaireQuestion,
)
from app.models.scoring import (
    MeasurementPillar,
    ParticipantDimensionScore,
    ParticipantImpactScore,
    ScoringDimension,
    ScoringFramework,
    ScoringRule,
)
from app.repositories.participant import EventRepository, ParticipantRepository
from app.schemas.scoring import (
    EventBulkCalculationResult,
    ParticipantDimensionScoreRead,
    ParticipantImpactScoreRead,
    ScoringDimensionRead,
    ScoringFrameworkCreate,
    ScoringFrameworkRead,
    ScoringFrameworkUpdate,
    ScoringRuleRead,
)
from app.scoring.calculator import calculate_impact_score
from app.services.audit_service import record_audit


def serialize_framework(fw: ScoringFramework) -> ScoringFrameworkRead:
    return ScoringFrameworkRead(
        id=fw.id,
        name=fw.name,
        version=fw.version,
        description=fw.description,
        is_active=fw.is_active,
        min_questions_per_pillar=fw.min_questions_per_pillar,
        min_pillars_required=fw.min_pillars_required,
        min_completeness_ratio=fw.min_completeness_ratio,
        effective_from=fw.effective_from,
        effective_to=fw.effective_to,
        dimensions=[
            ScoringDimensionRead(
                id=d.id,
                pillar_id=d.pillar_id,
                pillar_code=d.pillar.code if d.pillar else None,
                pillar_name=d.pillar.name if d.pillar else None,
                weight=d.weight,
                impact_category=d.impact_category,
                min_questions_required=d.min_questions_required,
            )
            for d in fw.dimensions
        ],
        rules=[ScoringRuleRead.model_validate(r) for r in fw.rules],
        created_at=fw.created_at,
    )


def serialize_impact_score(score: ParticipantImpactScore) -> ParticipantImpactScoreRead:
    return ParticipantImpactScoreRead(
        id=score.id,
        participant_id=score.participant_id,
        event_id=score.event_id,
        framework_id=score.framework_id,
        framework_version=score.framework_version,
        assessment_submission_id=score.assessment_submission_id,
        score_scope=score.score_scope,
        status=score.status,
        overall_impact_score=score.overall_impact_score,
        immediate_impact_score=score.immediate_impact_score,
        post_event_application_score=score.post_event_application_score,
        sustained_impact_score=score.sustained_impact_score,
        completeness_ratio=score.completeness_ratio,
        covered_pillars_count=score.covered_pillars_count,
        total_pillars_count=score.total_pillars_count,
        weight_renormalised=score.weight_renormalised,
        is_latest=score.is_latest,
        calculated_at=score.calculated_at,
        calculation_metadata=score.calculation_metadata,
        dimension_scores=[
            ParticipantDimensionScoreRead(
                id=ds.id,
                dimension_id=ds.dimension_id,
                pillar_id=ds.pillar_id,
                pillar_code=ds.pillar.code,
                pillar_name=ds.pillar.name,
                raw_score=ds.raw_score,
                normalised_score=ds.normalised_score,
                configured_weight=ds.configured_weight,
                effective_weight=ds.effective_weight,
                questions_answered=ds.questions_answered,
                questions_total=ds.questions_total,
                completeness_ratio=ds.completeness_ratio,
                status=ds.status,
            )
            for ds in score.dimension_scores
        ],
    )


class ScoringService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.participant_repo = ParticipantRepository(db)
        self.event_repo = EventRepository(db)

    def list_pillars(self) -> list[MeasurementPillar]:
        return list(
            self.db.execute(
                select(MeasurementPillar)
                .where(MeasurementPillar.is_active.is_(True))
                .order_by(MeasurementPillar.display_order.asc())
            )
            .scalars()
            .all()
        )

    def _load_framework(self, framework_id: UUID | None = None) -> ScoringFramework:
        stmt = select(ScoringFramework).options(
            selectinload(ScoringFramework.dimensions).selectinload(
                ScoringDimension.pillar
            ),
            selectinload(ScoringFramework.rules),
        )
        if framework_id is not None:
            fw = self.db.execute(
                stmt.where(ScoringFramework.id == framework_id)
            ).scalar_one_or_none()
            if fw is None:
                raise NotFoundError("ScoringFramework", framework_id)
            return fw

        fw = (
            self.db.execute(
                stmt.where(ScoringFramework.is_active.is_(True)).order_by(
                    ScoringFramework.effective_from.desc()
                )
            )
            .scalars()
            .first()
        )
        if fw is None:
            raise NotFoundError("Active ScoringFramework")
        return fw

    def list_frameworks(self) -> list[ScoringFrameworkRead]:
        stmt = (
            select(ScoringFramework)
            .options(
                selectinload(ScoringFramework.dimensions).selectinload(
                    ScoringDimension.pillar
                ),
                selectinload(ScoringFramework.rules),
            )
            .order_by(ScoringFramework.created_at.desc())
        )
        items = self.db.execute(stmt).scalars().all()
        return [serialize_framework(fw) for fw in items]

    def create_framework(
        self, payload: ScoringFrameworkCreate, *, actor: ActorContext
    ) -> ScoringFrameworkRead:
        existing = self.db.execute(
            select(ScoringFramework).where(
                ScoringFramework.name == payload.name,
                ScoringFramework.version == payload.version,
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError(
                f"Scoring framework '{payload.name}' version '{payload.version}' already exists."
            )

        fw = ScoringFramework(
            name=payload.name,
            version=payload.version,
            description=payload.description,
            is_active=payload.is_active,
            min_questions_per_pillar=payload.min_questions_per_pillar,
            min_pillars_required=payload.min_pillars_required,
            min_completeness_ratio=payload.min_completeness_ratio,
        )
        self.db.add(fw)
        self.db.flush()

        dims_by_pillar: dict[UUID, ScoringDimension] = {}
        for d_in in payload.dimensions:
            pillar = self.db.get(MeasurementPillar, d_in.pillar_id)
            if pillar is None:
                raise NotFoundError("MeasurementPillar", d_in.pillar_id)
            dim = ScoringDimension(
                framework_id=fw.id,
                pillar_id=pillar.id,
                weight=d_in.weight,
                impact_category=d_in.impact_category.value,
                min_questions_required=d_in.min_questions_required,
            )
            self.db.add(dim)
            self.db.flush()
            dims_by_pillar[pillar.id] = dim

        for r_in in payload.rules:
            if r_in.pillar_id not in dims_by_pillar:
                raise ValidationAppError(
                    f"Rule references pillar '{r_in.pillar_id}' which is not configured in this framework."
                )
            question = self.db.get(Question, r_in.question_id)
            if question is None:
                raise NotFoundError("Question", r_in.question_id)
            self.db.add(
                ScoringRule(
                    framework_id=fw.id,
                    dimension_id=dims_by_pillar[r_in.pillar_id].id,
                    question_id=question.id,
                    rule_type=r_in.rule_type.value,
                    rule_config=r_in.rule_config,
                    question_weight=r_in.question_weight,
                    is_active=r_in.is_active,
                )
            )

        record_audit(
            self.db,
            actor=actor,
            action="scoring_framework.create",
            resource_type="scoring_framework",
            resource_id=str(fw.id),
            details={"name": fw.name, "version": fw.version},
        )
        self.db.commit()
        return serialize_framework(self._load_framework(fw.id))

    def update_framework(
        self, framework_id: UUID, payload: ScoringFrameworkUpdate, *, actor: ActorContext
    ) -> ScoringFrameworkRead:
        fw = self._load_framework(framework_id)
        updates = payload.model_dump(exclude_unset=True)
        dims_in = updates.pop("dimensions", None)
        rules_in = updates.pop("rules", None)

        for field, value in updates.items():
            setattr(fw, field, value)

        dims_by_pillar = {d.pillar_id: d for d in fw.dimensions}
        if dims_in is not None:
            for d_in in payload.dimensions or []:
                if d_in.pillar_id in dims_by_pillar:
                    dim = dims_by_pillar[d_in.pillar_id]
                    dim.weight = d_in.weight
                    dim.impact_category = d_in.impact_category.value
                    dim.min_questions_required = d_in.min_questions_required
                else:
                    pillar = self.db.get(MeasurementPillar, d_in.pillar_id)
                    if pillar is None:
                        raise NotFoundError("MeasurementPillar", d_in.pillar_id)
                    dim = ScoringDimension(
                        framework_id=fw.id,
                        pillar_id=pillar.id,
                        weight=d_in.weight,
                        impact_category=d_in.impact_category.value,
                        min_questions_required=d_in.min_questions_required,
                    )
                    self.db.add(dim)
                    self.db.flush()
                    dims_by_pillar[pillar.id] = dim

        if rules_in is not None:
            fw.rules.clear()
            self.db.flush()
            for r_in in payload.rules or []:
                if r_in.pillar_id not in dims_by_pillar:
                    raise ValidationAppError(
                        f"Rule references pillar '{r_in.pillar_id}' not present in framework."
                    )
                if self.db.get(Question, r_in.question_id) is None:
                    raise NotFoundError("Question", r_in.question_id)
                self.db.add(
                    ScoringRule(
                        framework_id=fw.id,
                        dimension_id=dims_by_pillar[r_in.pillar_id].id,
                        question_id=r_in.question_id,
                        rule_type=r_in.rule_type.value,
                        rule_config=r_in.rule_config,
                        question_weight=r_in.question_weight,
                        is_active=r_in.is_active,
                    )
                )

        record_audit(
            self.db,
            actor=actor,
            action="scoring_framework.update",
            resource_type="scoring_framework",
            resource_id=str(fw.id),
        )
        self.db.commit()
        return serialize_framework(self._load_framework(fw.id))

    def calculate_for_participant(
        self,
        *,
        participant_id: UUID,
        event_id: UUID,
        framework_id: UUID | None = None,
        assessment_submission_id: UUID | None = None,
        actor: ActorContext,
        commit: bool = True,
    ) -> ParticipantImpactScoreRead:
        if self.participant_repo.get_by_id(participant_id) is None:
            raise NotFoundError("Participant", participant_id)
        event_obj = self.event_repo.get_by_id(event_id)
        if event_obj is None:
            raise NotFoundError("Event", event_id)

        effective_fw_id = framework_id or event_obj.active_framework_id
        fw = self._load_framework(effective_fw_id)

        # Fetch relevant submissions (specific submission or all submissions for participant+event)
        sub_stmt = (
            select(AssessmentSubmission)
            .options(selectinload(AssessmentSubmission.responses))
            .where(
                AssessmentSubmission.participant_id == participant_id,
                AssessmentSubmission.event_id == event_id,
            )
            .order_by(AssessmentSubmission.submitted_at.asc())
        )
        if assessment_submission_id is not None:
            sub_stmt = sub_stmt.where(AssessmentSubmission.id == assessment_submission_id)

        submissions = list(self.db.execute(sub_stmt).scalars().all())
        latest_submission_id = submissions[-1].id if submissions else assessment_submission_id

        # Latest response per question wins across multiple submissions for the same event
        responses_by_qid: dict[UUID, AssessmentResponse] = {}
        submitted_qn_ids: set[UUID] = set()
        for sub in submissions:
            submitted_qn_ids.add(sub.questionnaire_id)
            for resp in sub.responses:
                responses_by_qid[resp.question_id] = resp

        # Scope scoring rules to the submitted questionnaire(s) so rules from other
        # questionnaire versions/stages do not unfairly lower completeness_ratio
        scoped_rules = list(fw.rules)
        if submitted_qn_ids:
            qn_qids = set(
                self.db.execute(
                    select(QuestionnaireQuestion.question_id).where(
                        QuestionnaireQuestion.questionnaire_id.in_(submitted_qn_ids)
                    )
                )
                .scalars()
                .all()
            )
            matching_rules = [r for r in fw.rules if r.question_id in qn_qids]
            if matching_rules:
                scoped_rules = matching_rules

        rule_qids = {r.question_id for r in scoped_rules}
        questions_by_id: dict[UUID, Question] = {}
        if rule_qids:
            q_rows = (
                self.db.execute(
                    select(Question)
                    .options(selectinload(Question.options))
                    .where(Question.id.in_(rule_qids))
                )
                .scalars()
                .all()
            )
            questions_by_id = {q.id: q for q in q_rows}

        # Fetch longitudinal follow-ups, actions, and outcomes
        follow_ups = list(
            self.db.execute(
                select(FollowUpSubmission).where(
                    FollowUpSubmission.participant_id == participant_id,
                    FollowUpSubmission.event_id == event_id,
                )
            )
            .scalars()
            .all()
        )
        actions = list(
            self.db.execute(
                select(ParticipantAction).where(
                    ParticipantAction.participant_id == participant_id,
                    ParticipantAction.event_id == event_id,
                )
            )
            .scalars()
            .all()
        )
        outcomes = list(
            self.db.execute(
                select(ImpactOutcome).where(
                    ImpactOutcome.participant_id == participant_id,
                    ImpactOutcome.event_id == event_id,
                )
            )
            .scalars()
            .all()
        )

        computed = calculate_impact_score(
            framework=fw,
            dimensions=fw.dimensions,
            rules=scoped_rules,
            responses_by_question_id=responses_by_qid,
            questions_by_id=questions_by_id,
            follow_up_submissions=follow_ups,
            actions=actions,
            outcomes=outcomes,
        )

        # Preserve historical scores by marking previous latest record as historical
        self.db.execute(
            update(ParticipantImpactScore)
            .where(
                ParticipantImpactScore.participant_id == participant_id,
                ParticipantImpactScore.event_id == event_id,
                ParticipantImpactScore.is_latest.is_(True),
            )
            .values(is_latest=False)
        )

        impact_row = ParticipantImpactScore(
            participant_id=participant_id,
            event_id=event_id,
            framework_id=fw.id,
            framework_version=fw.version,
            assessment_submission_id=latest_submission_id,
            score_scope=ScoreScope.COMBINED.value,
            status=computed.status,
            overall_impact_score=computed.overall_impact_score,
            immediate_impact_score=computed.immediate_impact_score,
            post_event_application_score=computed.post_event_application_score,
            sustained_impact_score=computed.sustained_impact_score,
            completeness_ratio=computed.completeness_ratio,
            covered_pillars_count=computed.covered_pillars_count,
            total_pillars_count=computed.total_pillars_count,
            weight_renormalised=computed.weight_renormalised,
            is_latest=True,
            calculated_at=datetime.now(timezone.utc),
            calculation_metadata=computed.metadata,
        )
        self.db.add(impact_row)
        self.db.flush()

        for dim_res in computed.dimensions:
            self.db.add(
                ParticipantDimensionScore(
                    impact_score_id=impact_row.id,
                    participant_id=participant_id,
                    event_id=event_id,
                    dimension_id=dim_res.dimension_id,
                    pillar_id=dim_res.pillar_id,
                    raw_score=dim_res.raw_score,
                    normalised_score=dim_res.normalised_score,
                    configured_weight=dim_res.configured_weight,
                    effective_weight=dim_res.effective_weight,
                    questions_answered=dim_res.questions_answered,
                    questions_total=dim_res.questions_total,
                    completeness_ratio=dim_res.completeness_ratio,
                    status=dim_res.status,
                )
            )

        record_audit(
            self.db,
            actor=actor,
            action="scoring.calculate_participant",
            resource_type="participant_impact_score",
            resource_id=str(impact_row.id),
            details={
                "participant_id": str(participant_id),
                "event_id": str(event_id),
                "framework_version": fw.version,
                "status": computed.status,
                "overall_impact_score": computed.overall_impact_score,
            },
        )
        if commit:
            self.db.commit()
        else:
            self.db.flush()

        loaded = self.db.execute(
            select(ParticipantImpactScore)
            .options(
                selectinload(ParticipantImpactScore.dimension_scores).selectinload(
                    ParticipantDimensionScore.pillar
                )
            )
            .where(ParticipantImpactScore.id == impact_row.id)
        ).scalar_one()
        return serialize_impact_score(loaded)

    def calculate_for_event(
        self,
        *,
        event_id: UUID,
        framework_id: UUID | None = None,
        actor: ActorContext,
    ) -> EventBulkCalculationResult:
        if self.event_repo.get_by_id(event_id) is None:
            raise NotFoundError("Event", event_id)
        fw = self._load_framework(framework_id)

        # Union of registered participants and any participant with submissions for this event
        reg_pids = set(
            self.db.execute(
                select(EventRegistration.participant_id).where(
                    EventRegistration.event_id == event_id
                )
            )
            .scalars()
            .all()
        )
        sub_pids = set(
            self.db.execute(
                select(AssessmentSubmission.participant_id).where(
                    AssessmentSubmission.event_id == event_id
                )
            )
            .scalars()
            .all()
        )
        all_pids = sorted(reg_pids | sub_pids, key=str)

        results: list[ParticipantImpactScoreRead] = []
        for pid in all_pids:
            score = self.calculate_for_participant(
                participant_id=pid,
                event_id=event_id,
                framework_id=fw.id,
                actor=actor,
                commit=False,
            )
            results.append(score)

        self.db.commit()

        return EventBulkCalculationResult(
            event_id=event_id,
            framework_id=fw.id,
            framework_version=fw.version,
            participants_processed=len(results),
            calculated_count=sum(
                1 for r in results if r.status == ScoreStatus.CALCULATED.value
            ),
            partial_count=sum(
                1 for r in results if r.status == ScoreStatus.PARTIAL.value
            ),
            insufficient_data_count=sum(
                1 for r in results if r.status == ScoreStatus.INSUFFICIENT_DATA.value
            ),
            scores=results,
        )

    def get_participant_scores(
        self,
        participant_id: UUID,
        *,
        event_id: UUID | None = None,
        latest_only: bool = False,
    ) -> list[ParticipantImpactScoreRead]:
        if self.participant_repo.get_by_id(participant_id) is None:
            raise NotFoundError("Participant", participant_id)

        stmt = (
            select(ParticipantImpactScore)
            .options(
                selectinload(ParticipantImpactScore.dimension_scores).selectinload(
                    ParticipantDimensionScore.pillar
                )
            )
            .where(ParticipantImpactScore.participant_id == participant_id)
            .order_by(ParticipantImpactScore.calculated_at.desc())
        )
        if event_id is not None:
            stmt = stmt.where(ParticipantImpactScore.event_id == event_id)
        if latest_only:
            stmt = stmt.where(ParticipantImpactScore.is_latest.is_(True))

        rows = self.db.execute(stmt).scalars().all()
        return [serialize_impact_score(r) for r in rows]

    def get_event_scores(
        self, event_id: UUID, *, latest_only: bool = True
    ) -> list[ParticipantImpactScoreRead]:
        if self.event_repo.get_by_id(event_id) is None:
            raise NotFoundError("Event", event_id)

        stmt = (
            select(ParticipantImpactScore)
            .options(
                selectinload(ParticipantImpactScore.dimension_scores).selectinload(
                    ParticipantDimensionScore.pillar
                )
            )
            .where(ParticipantImpactScore.event_id == event_id)
            .order_by(ParticipantImpactScore.calculated_at.desc())
        )
        if latest_only:
            stmt = stmt.where(ParticipantImpactScore.is_latest.is_(True))

        rows = self.db.execute(stmt).scalars().all()
        return [serialize_impact_score(r) for r in rows]
