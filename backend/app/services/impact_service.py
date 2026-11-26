"""Longitudinal impact tracking service: Follow-Ups (30/60/90d), Actions, Connections & Evidence."""

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import (
    ActionStatus,
    EvidenceClassification,
    FollowUpStatus,
    VerificationStatus,
)
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.security import ActorContext
from app.models.impact import (
    FollowUpSchedule,
    FollowUpStageConfig,
    FollowUpSubmission,
    ImpactOutcome,
    OutcomeEvidence,
    ParticipantAction,
    ProfessionalConnection,
)
from app.models.participant import Participant
from app.repositories.participant import EventRepository, ParticipantRepository
from app.schemas.impact import (
    FollowUpScheduleCreate,
    FollowUpStageConfigCreate,
    FollowUpSubmitRequest,
    ImpactOutcomeCreate,
    ImpactOutcomeListItem,
    ImpactOutcomeRead,
    OutcomeEvidenceIn,
    OutcomeVerifyRequest,
    ParticipantActionCreate,
    ParticipantActionListItem,
    ParticipantActionRead,
    ParticipantActionUpdate,
    ParticipantImpactSummary,
    ProfessionalConnectionCreate,
    ProfessionalConnectionListItem,
    ProfessionalConnectionRead,
)
from app.scoring.service import ScoringService
from app.services.audit_service import record_audit


class ImpactTrackingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.participant_repo = ParticipantRepository(db)
        self.event_repo = EventRepository(db)

    # --- Configurable Follow-Up Stages ---
    def create_stage_config(
        self, payload: FollowUpStageConfigCreate, *, actor: ActorContext
    ) -> FollowUpStageConfig:
        if payload.event_id is not None and self.event_repo.get_by_id(payload.event_id) is None:
            raise NotFoundError("Event", payload.event_id)

        existing = self.db.execute(
            select(FollowUpStageConfig).where(
                FollowUpStageConfig.event_id == payload.event_id,
                FollowUpStageConfig.stage_code == payload.stage_code,
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError(
                f"Follow-up stage '{payload.stage_code}' already exists for this scope."
            )

        cfg = FollowUpStageConfig(**payload.model_dump())
        self.db.add(cfg)
        self.db.flush()
        record_audit(
            self.db,
            actor=actor,
            action="follow_up_stage.create",
            resource_type="follow_up_stage_config",
            resource_id=str(cfg.id),
            details={"stage_code": cfg.stage_code, "days_after_event": cfg.days_after_event},
        )
        self.db.commit()
        self.db.refresh(cfg)
        return cfg

    def list_stage_configs(self, event_id: UUID | None = None) -> list[FollowUpStageConfig]:
        stmt = select(FollowUpStageConfig).where(FollowUpStageConfig.is_active.is_(True))
        if event_id is not None:
            stmt = stmt.where(
                or_(
                    FollowUpStageConfig.event_id == event_id,
                    FollowUpStageConfig.event_id.is_(None),
                )
            )
        return list(
            self.db.execute(
                stmt.order_by(
                    FollowUpStageConfig.days_after_event.asc(),
                    FollowUpStageConfig.display_order.asc(),
                )
            )
            .scalars()
            .all()
        )

    # --- Follow-Up Schedules & Submissions ---
    def create_follow_up_schedules(
        self, payload: FollowUpScheduleCreate, *, actor: ActorContext
    ) -> list[FollowUpSchedule]:
        participant = self.participant_repo.get_by_id(payload.participant_id)
        if participant is None:
            raise NotFoundError("Participant", payload.participant_id)
        event = self.event_repo.get_by_id(payload.event_id)
        if event is None:
            raise NotFoundError("Event", payload.event_id)

        stage_configs = self.list_stage_configs(event_id=event.id)
        # Prefer event-specific stage config over global config with the same stage_code
        deduped_stages: dict[str, FollowUpStageConfig] = {}
        for cfg in stage_configs:
            if cfg.stage_code not in deduped_stages or cfg.event_id is not None:
                deduped_stages[cfg.stage_code] = cfg

        base_date = event.event_date or date.today()
        targets: list[tuple[str, FollowUpStageConfig | None, date]] = []
        if payload.follow_up_stage:
            cfg = deduped_stages.get(payload.follow_up_stage)
            due = (
                payload.due_date
                or (
                    base_date + timedelta(days=cfg.days_after_event)
                    if cfg
                    else base_date + timedelta(days=30)
                )
            )
            targets.append((payload.follow_up_stage, cfg, due))
        else:
            post_event_stages = {
                code: cfg
                for code, cfg in deduped_stages.items()
                if cfg.days_after_event > 0
            }
            if not post_event_stages:
                raise ValidationAppError(
                    "No active follow-up stage configurations found. Specify follow_up_stage explicitly."
                )
            for code, cfg in sorted(
                post_event_stages.items(), key=lambda kv: kv[1].days_after_event
            ):
                due = base_date + timedelta(days=cfg.days_after_event)
                targets.append((code, cfg, due))

        created: list[FollowUpSchedule] = []
        for stage_code, cfg, due in targets:
            existing = self.db.execute(
                select(FollowUpSchedule)
                .options(selectinload(FollowUpSchedule.submissions))
                .where(
                    FollowUpSchedule.participant_id == participant.id,
                    FollowUpSchedule.event_id == event.id,
                    FollowUpSchedule.follow_up_stage == stage_code,
                )
            ).scalar_one_or_none()
            if existing is not None:
                if payload.follow_up_stage:
                    raise ConflictError(
                        f"Follow-up schedule '{stage_code}' already exists for this participant and event."
                    )
                created.append(existing)
                continue

            sched = FollowUpSchedule(
                participant_id=participant.id,
                event_id=event.id,
                stage_config_id=cfg.id if cfg else None,
                follow_up_stage=stage_code,
                due_date=due,
                status=payload.status.value,
            )
            self.db.add(sched)
            self.db.flush()
            created.append(sched)

        record_audit(
            self.db,
            actor=actor,
            action="follow_up.schedule",
            resource_type="follow_up_schedule",
            resource_id=str(created[0].id) if created else None,
            details={
                "participant_id": str(participant.id),
                "event_id": str(event.id),
                "stages": [s.follow_up_stage for s in created],
            },
        )
        self.db.commit()

        ids = [s.id for s in created]
        return list(
            self.db.execute(
                select(FollowUpSchedule)
                .options(selectinload(FollowUpSchedule.submissions))
                .where(FollowUpSchedule.id.in_(ids))
                .order_by(FollowUpSchedule.due_date.asc())
            )
            .scalars()
            .all()
        )

    def list_follow_ups(
        self,
        *,
        event_id: UUID | None = None,
        participant_id: UUID | None = None,
        follow_up_stage: str | None = None,
        status: str | None = None,
    ) -> list[FollowUpSchedule]:
        stmt = select(FollowUpSchedule).options(
            selectinload(FollowUpSchedule.submissions)
        )
        if event_id is not None:
            stmt = stmt.where(FollowUpSchedule.event_id == event_id)
        if participant_id is not None:
            stmt = stmt.where(FollowUpSchedule.participant_id == participant_id)
        if follow_up_stage is not None:
            stmt = stmt.where(FollowUpSchedule.follow_up_stage == follow_up_stage)
        if status is not None:
            stmt = stmt.where(FollowUpSchedule.status == status)
        return list(
            self.db.execute(stmt.order_by(FollowUpSchedule.due_date.asc())).scalars().all()
        )

    def submit_follow_up(
        self,
        follow_up_id: UUID,
        payload: FollowUpSubmitRequest,
        *,
        actor: ActorContext,
    ) -> FollowUpSubmission:
        schedule = self.db.get(FollowUpSchedule, follow_up_id)
        if schedule is None:
            raise NotFoundError("FollowUpSchedule", follow_up_id)

        # Enforce Scenario E: without supporting evidence, classification is strictly self_reported
        has_evidence = len(payload.evidence_items) > 0
        if has_evidence:
            evidence_cls = EvidenceClassification.DOCUMENTED.value
            ver_status = VerificationStatus.PENDING_REVIEW.value
        else:
            evidence_cls = EvidenceClassification.SELF_REPORTED.value
            ver_status = VerificationStatus.UNVERIFIED.value

        # Allow admins to explicitly classify as verified if submitting audited records
        if actor.is_admin and payload.evidence_classification == EvidenceClassification.VERIFIED:
            evidence_cls = EvidenceClassification.VERIFIED.value
            ver_status = VerificationStatus.VERIFIED.value

        now = datetime.now(timezone.utc)
        sub = FollowUpSubmission(
            follow_up_schedule_id=schedule.id,
            participant_id=schedule.participant_id,
            event_id=schedule.event_id,
            follow_up_stage=schedule.follow_up_stage,
            assessment_submission_id=payload.assessment_submission_id,
            assessment_date=payload.assessment_date or date.today(),
            responses_json=payload.responses,
            reported_actions_json=[
                a.model_dump(mode="json") for a in payload.reported_actions
            ],
            outcome_descriptions=payload.outcome_descriptions,
            evidence_classification=evidence_cls,
            verification_status=ver_status,
            verified_by=actor.actor_id if ver_status == VerificationStatus.VERIFIED.value else None,
            verified_at=now if ver_status == VerificationStatus.VERIFIED.value else None,
            submitted_at=now,
        )
        self.db.add(sub)
        self.db.flush()

        # Mark ONLY this stage as completed; other stages (e.g., 60_day, 90_day) remain untouched (Scenario F)
        schedule.status = FollowUpStatus.COMPLETED.value
        schedule.completed_at = now

        # Persist structured ParticipantAction rows (preserving intended vs completed distinction — Scenario D)
        for act in payload.reported_actions:
            self.db.add(
                ParticipantAction(
                    participant_id=schedule.participant_id,
                    event_id=schedule.event_id,
                    follow_up_submission_id=sub.id,
                    action_category=act.action_category.value,
                    title=act.title,
                    description=act.description,
                    action_status=act.action_status.value,
                    target_date=act.target_date,
                    completed_at=now if act.action_status == ActionStatus.COMPLETED else None,
                    evidence_classification=act.evidence_classification.value,
                )
            )

        # Persist structured ImpactOutcome + OutcomeEvidence if outcome_descriptions supplied
        if payload.outcome_descriptions and payload.outcome_descriptions.strip():
            outcome = ImpactOutcome(
                participant_id=schedule.participant_id,
                event_id=schedule.event_id,
                follow_up_submission_id=sub.id,
                outcome_type=payload.outcome_type.value,
                title=f"{schedule.follow_up_stage} reported outcome",
                description=payload.outcome_descriptions.strip(),
                evidence_classification=evidence_cls,
                verification_status=ver_status,
                observed_at=sub.assessment_date,
            )
            self.db.add(outcome)
            self.db.flush()
            for ev in payload.evidence_items:
                self.db.add(
                    OutcomeEvidence(
                        outcome_id=outcome.id,
                        evidence_type=ev.evidence_type,
                        description=ev.description,
                        reference_url=ev.reference_url,
                        submitted_by=actor.actor_id,
                    )
                )

        record_audit(
            self.db,
            actor=actor,
            action="follow_up.submit",
            resource_type="follow_up_submission",
            resource_id=str(sub.id),
            details={
                "participant_id": str(schedule.participant_id),
                "event_id": str(schedule.event_id),
                "stage": schedule.follow_up_stage,
                "evidence_classification": evidence_cls,
            },
        )
        self.db.commit()
        self.db.refresh(sub)

        # Refresh participant impact score with new longitudinal follow-up evidence
        try:
            ScoringService(self.db).calculate_for_participant(
                participant_id=schedule.participant_id,
                event_id=schedule.event_id,
                actor=actor,
            )
        except NotFoundError:
            pass

        return sub

    def get_participant_follow_ups(
        self, participant_id: UUID, *, event_id: UUID | None = None
    ) -> list[FollowUpSchedule]:
        if self.participant_repo.get_by_id(participant_id) is None:
            raise NotFoundError("Participant", participant_id)
        return self.list_follow_ups(participant_id=participant_id, event_id=event_id)

    # --- Participant Actions (Intention vs Implementation) ---
    def create_action(
        self, payload: ParticipantActionCreate, *, actor: ActorContext
    ) -> ParticipantAction:
        if self.participant_repo.get_by_id(payload.participant_id) is None:
            raise NotFoundError("Participant", payload.participant_id)
        if self.event_repo.get_by_id(payload.event_id) is None:
            raise NotFoundError("Event", payload.event_id)

        action = ParticipantAction(
            participant_id=payload.participant_id,
            event_id=payload.event_id,
            follow_up_submission_id=payload.follow_up_submission_id,
            action_category=payload.action_category.value,
            title=payload.title,
            description=payload.description,
            action_status=payload.action_status.value,
            target_date=payload.target_date,
            completed_at=datetime.now(timezone.utc)
            if payload.action_status == ActionStatus.COMPLETED
            else None,
            evidence_classification=payload.evidence_classification.value,
        )
        self.db.add(action)
        self.db.flush()
        record_audit(
            self.db,
            actor=actor,
            action="participant_action.create",
            resource_type="participant_action",
            resource_id=str(action.id),
            details={"action_status": action.action_status},
        )
        self.db.commit()
        self.db.refresh(action)
        return action

    def update_action(
        self, action_id: UUID, payload: ParticipantActionUpdate, *, actor: ActorContext
    ) -> ParticipantAction:
        action = self.db.get(ParticipantAction, action_id)
        if action is None:
            raise NotFoundError("ParticipantAction", action_id)
        updates = payload.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(action, field, value.value if hasattr(value, "value") else value)
        if payload.action_status == ActionStatus.COMPLETED and action.completed_at is None:
            action.completed_at = datetime.now(timezone.utc)
        record_audit(
            self.db,
            actor=actor,
            action="participant_action.update",
            resource_type="participant_action",
            resource_id=str(action.id),
            details={"action_status": action.action_status},
        )
        self.db.commit()
        self.db.refresh(action)
        return action

    # --- Professional Connections ---
    def create_connection(
        self, payload: ProfessionalConnectionCreate, *, actor: ActorContext
    ) -> ProfessionalConnection:
        if self.participant_repo.get_by_id(payload.participant_id) is None:
            raise NotFoundError("Participant", payload.participant_id)
        if self.event_repo.get_by_id(payload.event_id) is None:
            raise NotFoundError("Event", payload.event_id)

        conn = ProfessionalConnection(
            participant_id=payload.participant_id,
            event_id=payload.event_id,
            connected_participant_id=payload.connected_participant_id,
            contact_name=payload.contact_name,
            contact_role=payload.contact_role,
            connection_type=payload.connection_type.value,
            follow_up_occurred=payload.follow_up_occurred,
            collaboration_started=payload.collaboration_started,
            opportunity_discovered=payload.opportunity_discovered,
            notes=payload.notes,
            evidence_classification=payload.evidence_classification.value,
        )
        self.db.add(conn)
        self.db.flush()
        record_audit(
            self.db,
            actor=actor,
            action="professional_connection.create",
            resource_type="professional_connection",
            resource_id=str(conn.id),
        )
        self.db.commit()
        self.db.refresh(conn)
        return conn

    # --- Impact Outcomes & Evidence Verification ---
    def create_outcome(
        self, payload: ImpactOutcomeCreate, *, actor: ActorContext
    ) -> ImpactOutcome:
        if self.participant_repo.get_by_id(payload.participant_id) is None:
            raise NotFoundError("Participant", payload.participant_id)
        if self.event_repo.get_by_id(payload.event_id) is None:
            raise NotFoundError("Event", payload.event_id)

        # Scenario E: Outcomes without evidence are strictly self-reported
        has_evidence = len(payload.evidence_items) > 0
        evidence_cls = (
            EvidenceClassification.DOCUMENTED.value
            if has_evidence
            else EvidenceClassification.SELF_REPORTED.value
        )
        ver_status = (
            VerificationStatus.PENDING_REVIEW.value
            if has_evidence
            else VerificationStatus.UNVERIFIED.value
        )

        outcome = ImpactOutcome(
            participant_id=payload.participant_id,
            event_id=payload.event_id,
            follow_up_submission_id=payload.follow_up_submission_id,
            action_id=payload.action_id,
            outcome_type=payload.outcome_type.value,
            title=payload.title,
            description=payload.description,
            evidence_classification=evidence_cls,
            verification_status=ver_status,
            observed_at=payload.observed_at or date.today(),
        )
        self.db.add(outcome)
        self.db.flush()

        for ev in payload.evidence_items:
            self.db.add(
                OutcomeEvidence(
                    outcome_id=outcome.id,
                    evidence_type=ev.evidence_type,
                    description=ev.description,
                    reference_url=ev.reference_url,
                    submitted_by=actor.actor_id,
                )
            )

        record_audit(
            self.db,
            actor=actor,
            action="impact_outcome.create",
            resource_type="impact_outcome",
            resource_id=str(outcome.id),
            details={"evidence_classification": evidence_cls},
        )
        self.db.commit()
        return self.db.execute(
            select(ImpactOutcome)
            .options(selectinload(ImpactOutcome.evidence_items))
            .where(ImpactOutcome.id == outcome.id)
        ).scalar_one()

    def attach_evidence(
        self, outcome_id: UUID, payload: OutcomeEvidenceIn, *, actor: ActorContext
    ) -> ImpactOutcome:
        outcome = self.db.execute(
            select(ImpactOutcome)
            .options(selectinload(ImpactOutcome.evidence_items))
            .where(ImpactOutcome.id == outcome_id)
        ).scalar_one_or_none()
        if outcome is None:
            raise NotFoundError("ImpactOutcome", outcome_id)

        self.db.add(
            OutcomeEvidence(
                outcome_id=outcome.id,
                evidence_type=payload.evidence_type,
                description=payload.description,
                reference_url=payload.reference_url,
                submitted_by=actor.actor_id,
            )
        )
        if outcome.evidence_classification == EvidenceClassification.SELF_REPORTED.value:
            outcome.evidence_classification = EvidenceClassification.DOCUMENTED.value
        if outcome.verification_status == VerificationStatus.UNVERIFIED.value:
            outcome.verification_status = VerificationStatus.PENDING_REVIEW.value

        self.db.commit()
        return self.db.execute(
            select(ImpactOutcome)
            .options(selectinload(ImpactOutcome.evidence_items))
            .where(ImpactOutcome.id == outcome.id)
        ).scalar_one()

    def verify_outcome(
        self, outcome_id: UUID, payload: OutcomeVerifyRequest, *, actor: ActorContext
    ) -> ImpactOutcome:
        outcome = self.db.execute(
            select(ImpactOutcome)
            .options(selectinload(ImpactOutcome.evidence_items))
            .where(ImpactOutcome.id == outcome_id)
        ).scalar_one_or_none()
        if outcome is None:
            raise NotFoundError("ImpactOutcome", outcome_id)

        now = datetime.now(timezone.utc)
        outcome.verification_status = payload.verification_status.value
        if payload.verification_status == VerificationStatus.VERIFIED:
            outcome.evidence_classification = EvidenceClassification.VERIFIED.value
            for ev in outcome.evidence_items:
                ev.verified_by = actor.actor_id
                ev.verified_at = now
                ev.verification_notes = payload.verification_notes
        elif payload.verification_status == VerificationStatus.REJECTED:
            outcome.evidence_classification = EvidenceClassification.SELF_REPORTED.value

        record_audit(
            self.db,
            actor=actor,
            action="impact_outcome.verify",
            resource_type="impact_outcome",
            resource_id=str(outcome.id),
            details={
                "verification_status": outcome.verification_status,
                "evidence_classification": outcome.evidence_classification,
            },
        )
        self.db.commit()
        return self.db.execute(
            select(ImpactOutcome)
            .options(selectinload(ImpactOutcome.evidence_items))
            .where(ImpactOutcome.id == outcome.id)
        ).scalar_one()

    # --- Admin Listing Methods for Actions, Connections, and Outcomes ---
    def list_actions(
        self,
        *,
        event_id: UUID | None = None,
        participant_id: UUID | None = None,
        action_status: str | None = None,
        action_category: str | None = None,
        evidence_classification: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ParticipantActionListItem], int]:
        stmt = select(ParticipantAction, Participant.full_name).join(
            Participant, Participant.id == ParticipantAction.participant_id
        )
        count_stmt = select(func.count(ParticipantAction.id))

        if event_id is not None:
            stmt = stmt.where(ParticipantAction.event_id == event_id)
            count_stmt = count_stmt.where(ParticipantAction.event_id == event_id)
        if participant_id is not None:
            stmt = stmt.where(ParticipantAction.participant_id == participant_id)
            count_stmt = count_stmt.where(
                ParticipantAction.participant_id == participant_id
            )
        if action_status is not None:
            stmt = stmt.where(ParticipantAction.action_status == action_status)
            count_stmt = count_stmt.where(ParticipantAction.action_status == action_status)
        if action_category is not None:
            stmt = stmt.where(ParticipantAction.action_category == action_category)
            count_stmt = count_stmt.where(
                ParticipantAction.action_category == action_category
            )
        if evidence_classification is not None:
            stmt = stmt.where(
                ParticipantAction.evidence_classification == evidence_classification
            )
            count_stmt = count_stmt.where(
                ParticipantAction.evidence_classification == evidence_classification
            )

        total = int(self.db.execute(count_stmt).scalar_one())
        rows = self.db.execute(
            stmt.order_by(ParticipantAction.created_at.desc()).limit(limit).offset(offset)
        ).all()
        items = [
            ParticipantActionListItem(
                **ParticipantActionRead.model_validate(action).model_dump(),
                participant_name=p_name,
            )
            for action, p_name in rows
        ]
        return items, total

    def list_connections(
        self,
        *,
        event_id: UUID | None = None,
        participant_id: UUID | None = None,
        connection_type: str | None = None,
        evidence_classification: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ProfessionalConnectionListItem], int]:
        stmt = select(ProfessionalConnection, Participant.full_name).join(
            Participant, Participant.id == ProfessionalConnection.participant_id
        )
        count_stmt = select(func.count(ProfessionalConnection.id))

        if event_id is not None:
            stmt = stmt.where(ProfessionalConnection.event_id == event_id)
            count_stmt = count_stmt.where(ProfessionalConnection.event_id == event_id)
        if participant_id is not None:
            stmt = stmt.where(ProfessionalConnection.participant_id == participant_id)
            count_stmt = count_stmt.where(
                ProfessionalConnection.participant_id == participant_id
            )
        if connection_type is not None:
            stmt = stmt.where(ProfessionalConnection.connection_type == connection_type)
            count_stmt = count_stmt.where(
                ProfessionalConnection.connection_type == connection_type
            )
        if evidence_classification is not None:
            stmt = stmt.where(
                ProfessionalConnection.evidence_classification == evidence_classification
            )
            count_stmt = count_stmt.where(
                ProfessionalConnection.evidence_classification == evidence_classification
            )

        total = int(self.db.execute(count_stmt).scalar_one())
        rows = self.db.execute(
            stmt.order_by(ProfessionalConnection.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        items = [
            ProfessionalConnectionListItem(
                **ProfessionalConnectionRead.model_validate(conn).model_dump(),
                participant_name=p_name,
            )
            for conn, p_name in rows
        ]
        return items, total

    def list_outcomes(
        self,
        *,
        event_id: UUID | None = None,
        participant_id: UUID | None = None,
        outcome_type: str | None = None,
        evidence_classification: str | None = None,
        verification_status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ImpactOutcomeListItem], int]:
        stmt = (
            select(ImpactOutcome, Participant.full_name)
            .join(Participant, Participant.id == ImpactOutcome.participant_id)
            .options(selectinload(ImpactOutcome.evidence_items))
        )
        count_stmt = select(func.count(ImpactOutcome.id))

        if event_id is not None:
            stmt = stmt.where(ImpactOutcome.event_id == event_id)
            count_stmt = count_stmt.where(ImpactOutcome.event_id == event_id)
        if participant_id is not None:
            stmt = stmt.where(ImpactOutcome.participant_id == participant_id)
            count_stmt = count_stmt.where(ImpactOutcome.participant_id == participant_id)
        if outcome_type is not None:
            stmt = stmt.where(ImpactOutcome.outcome_type == outcome_type)
            count_stmt = count_stmt.where(ImpactOutcome.outcome_type == outcome_type)
        if evidence_classification is not None:
            stmt = stmt.where(
                ImpactOutcome.evidence_classification == evidence_classification
            )
            count_stmt = count_stmt.where(
                ImpactOutcome.evidence_classification == evidence_classification
            )
        if verification_status is not None:
            stmt = stmt.where(ImpactOutcome.verification_status == verification_status)
            count_stmt = count_stmt.where(
                ImpactOutcome.verification_status == verification_status
            )

        total = int(self.db.execute(count_stmt).scalar_one())
        rows = self.db.execute(
            stmt.order_by(ImpactOutcome.created_at.desc()).limit(limit).offset(offset)
        ).all()
        items = [
            ImpactOutcomeListItem(
                **ImpactOutcomeRead.model_validate(outcome).model_dump(),
                participant_name=p_name,
            )
            for outcome, p_name in rows
        ]
        return items, total

    # --- Participant Holistic Impact View (/participants/{id}/impact) ---
    def get_participant_impact_summary(
        self, participant_id: UUID, *, event_id: UUID | None = None
    ) -> ParticipantImpactSummary:
        if self.participant_repo.get_by_id(participant_id) is None:
            raise NotFoundError("Participant", participant_id)

        scoring_svc = ScoringService(self.db)
        latest_scores = scoring_svc.get_participant_scores(
            participant_id, event_id=event_id, latest_only=True
        )

        act_stmt = select(ParticipantAction).where(
            ParticipantAction.participant_id == participant_id
        )
        conn_stmt = select(ProfessionalConnection).where(
            ProfessionalConnection.participant_id == participant_id
        )
        out_stmt = select(ImpactOutcome).where(
            ImpactOutcome.participant_id == participant_id
        )
        if event_id is not None:
            act_stmt = act_stmt.where(ParticipantAction.event_id == event_id)
            conn_stmt = conn_stmt.where(ProfessionalConnection.event_id == event_id)
            out_stmt = out_stmt.where(ImpactOutcome.event_id == event_id)

        actions = list(self.db.execute(act_stmt).scalars().all())
        connections = list(self.db.execute(conn_stmt).scalars().all())
        outcomes = list(self.db.execute(out_stmt).scalars().all())
        follow_ups = self.list_follow_ups(participant_id=participant_id, event_id=event_id)

        return ParticipantImpactSummary(
            participant_id=participant_id,
            event_id=event_id,
            latest_scores=[s.model_dump(mode="json") for s in latest_scores],
            actions_summary={
                status.value: sum(1 for a in actions if a.action_status == status.value)
                for status in ActionStatus
            },
            connections_summary={
                "total": len(connections),
                "follow_ups_occurred": sum(1 for c in connections if c.follow_up_occurred),
                "collaborations_started": sum(
                    1 for c in connections if c.collaboration_started
                ),
                "opportunities_discovered": sum(
                    1 for c in connections if c.opportunity_discovered
                ),
            },
            outcomes_by_evidence={
                ev.value: sum(
                    1 for o in outcomes if o.evidence_classification == ev.value
                )
                for ev in EvidenceClassification
            },
            follow_up_progress=[
                {
                    "schedule_id": str(fu.id),
                    "event_id": str(fu.event_id),
                    "follow_up_stage": fu.follow_up_stage,
                    "due_date": fu.due_date.isoformat(),
                    "status": fu.status,
                    "completed_at": fu.completed_at.isoformat() if fu.completed_at else None,
                    "submissions_count": len(fu.submissions),
                }
                for fu in follow_ups
            ],
        )
