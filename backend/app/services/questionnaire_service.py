"""Services for Question Cards, Questions, Questionnaires, and Assessment Submissions."""

from datetime import date, datetime, time, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import (
    QuestionType,
    QuestionnaireStatus,
    RegistrationSource,
    RegistrationStatus,
    SubmissionStatus,
)
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.normalisation import normalise_email, normalise_phone
from app.core.security import ActorContext
from app.models.participant import Event, EventRegistration, Participant
from app.models.questionnaire import (
    AssessmentResponse,
    AssessmentSubmission,
    Question,
    QuestionCard,
    QuestionCategory,
    Questionnaire,
    QuestionnaireQuestion,
    QuestionnaireSection,
    QuestionOption,
    QuestionPillarMapping,
)
from app.models.scoring import MeasurementPillar
from app.repositories.participant import EventRepository, ParticipantRepository
from app.repositories.questionnaire import (
    AssessmentRepository,
    QuestionCardRepository,
    QuestionnaireRepository,
    QuestionRepository,
)
from app.schemas.questionnaire import (
    AssessmentResponseIn,
    AssessmentSubmitRequest,
    AssessmentSummaryRead,
    FeedbackResponseRead,
    QuestionCardCreate,
    QuestionCardRead,
    QuestionCardUpdate,
    QuestionCreate,
    QuestionnaireCreate,
    QuestionnaireQuestionRead,
    QuestionnaireRead,
    QuestionnaireSectionRead,
    QuestionnaireUpdate,
    QuestionOptionRead,
    QuestionRead,
    QuestionUpdate,
)
from app.services.audit_service import record_audit


def serialize_question(q: Question) -> QuestionRead:
    return QuestionRead(
        id=q.id,
        card_id=q.card_id,
        category_id=q.category_id,
        code=q.code,
        question_text=q.question_text,
        description=q.description,
        question_type=q.question_type,
        category=q.category,
        is_required=q.is_required,
        is_scorable=q.is_scorable,
        allow_explanation=q.allow_explanation,
        explanation_prompt=q.explanation_prompt,
        validation_config=q.validation_config,
        scoring_config=q.scoring_config,
        display_order=q.display_order,
        is_archived=q.is_archived,
        archived_at=q.archived_at,
        pillar_ids=[m.pillar_id for m in q.pillar_mappings],
        options=[QuestionOptionRead.model_validate(opt) for opt in q.options],
        created_at=q.created_at,
        updated_at=q.updated_at,
    )


def serialize_card(card: QuestionCard) -> QuestionCardRead:
    return QuestionCardRead(
        id=card.id,
        code=card.code,
        title=card.title,
        description=card.description,
        category=card.category,
        is_active=card.is_active,
        display_order=card.display_order,
        questions=[serialize_question(q) for q in card.questions if not q.is_archived],
        created_at=card.created_at,
        updated_at=card.updated_at,
    )


def serialize_questionnaire(qn: Questionnaire) -> QuestionnaireRead:
    return QuestionnaireRead(
        id=qn.id,
        event_id=qn.event_id,
        code=qn.code,
        title=qn.title,
        description=qn.description,
        questionnaire_type=qn.questionnaire_type,
        assessment_stage=qn.assessment_stage,
        version=qn.version,
        status=qn.status,
        published_at=qn.published_at,
        sections=[QuestionnaireSectionRead.model_validate(s) for s in qn.sections],
        questions=[
            QuestionnaireQuestionRead(
                id=link.id,
                section_id=link.section_id,
                question_id=link.question_id,
                is_required_override=link.is_required_override,
                display_order=link.display_order,
                question=serialize_question(link.question),
            )
            for link in qn.questionnaire_questions
        ],
        created_at=qn.created_at,
        updated_at=qn.updated_at,
    )


class QuestionEngineService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.card_repo = QuestionCardRepository(db)
        self.question_repo = QuestionRepository(db)
        self.questionnaire_repo = QuestionnaireRepository(db)
        self.assessment_repo = AssessmentRepository(db)
        self.participant_repo = ParticipantRepository(db)
        self.event_repo = EventRepository(db)

    # --- Question Cards ---
    def create_card(
        self, payload: QuestionCardCreate, *, actor: ActorContext
    ) -> QuestionCardRead:
        if self.card_repo.get_by_code(payload.code) is not None:
            raise ConflictError(f"Question card with code '{payload.code}' already exists.")
        card = QuestionCard(**payload.model_dump())
        self.db.add(card)
        self.db.flush()
        record_audit(
            self.db,
            actor=actor,
            action="question_card.create",
            resource_type="question_card",
            resource_id=str(card.id),
            details={"code": card.code},
        )
        self.db.commit()
        return serialize_card(self.card_repo.get_by_id(card.id))  # type: ignore[arg-type]

    def list_cards(self, *, include_inactive: bool = False) -> list[QuestionCardRead]:
        return [
            serialize_card(c)
            for c in self.card_repo.list_cards(include_inactive=include_inactive)
        ]

    def get_card(self, card_id: UUID) -> QuestionCardRead:
        card = self.card_repo.get_by_id(card_id)
        if card is None:
            raise NotFoundError("QuestionCard", card_id)
        return serialize_card(card)

    def update_card(
        self, card_id: UUID, payload: QuestionCardUpdate, *, actor: ActorContext
    ) -> QuestionCardRead:
        card = self.card_repo.get_by_id(card_id)
        if card is None:
            raise NotFoundError("QuestionCard", card_id)
        updates = payload.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(card, field, value)
        record_audit(
            self.db,
            actor=actor,
            action="question_card.update",
            resource_type="question_card",
            resource_id=str(card.id),
            details={"updated_fields": sorted(updates.keys())},
        )
        self.db.commit()
        return serialize_card(self.card_repo.get_by_id(card.id))  # type: ignore[arg-type]

    # --- Questions ---
    def _validate_pillar_ids(self, pillar_ids: list[UUID]) -> None:
        for pid in pillar_ids:
            if self.db.get(MeasurementPillar, pid) is None:
                raise NotFoundError("MeasurementPillar", pid)

    def list_categories(self) -> list[QuestionCategory]:
        return list(
            self.db.execute(
                select(QuestionCategory)
                .where(QuestionCategory.is_active.is_(True))
                .order_by(QuestionCategory.display_order.asc())
            )
            .scalars()
            .all()
        )

    def create_question(
        self, payload: QuestionCreate, *, actor: ActorContext
    ) -> QuestionRead:
        if self.question_repo.get_by_code(payload.code) is not None:
            raise ConflictError(f"Question with code '{payload.code}' already exists.")
        if payload.card_id is not None and self.card_repo.get_by_id(payload.card_id) is None:
            raise NotFoundError("QuestionCard", payload.card_id)
        self._validate_pillar_ids(payload.pillar_ids)

        question = Question(
            card_id=payload.card_id,
            category_id=payload.category_id,
            code=payload.code,
            question_text=payload.question_text,
            description=payload.description,
            question_type=payload.question_type.value,
            category=payload.category,
            is_required=payload.is_required,
            is_scorable=payload.is_scorable,
            allow_explanation=payload.allow_explanation,
            explanation_prompt=payload.explanation_prompt,
            validation_config=payload.validation_config,
            scoring_config=payload.scoring_config,
            display_order=payload.display_order,
        )
        self.db.add(question)
        self.db.flush()

        for idx, pid in enumerate(dict.fromkeys(payload.pillar_ids)):
            self.db.add(
                QuestionPillarMapping(
                    question_id=question.id, pillar_id=pid, is_primary=(idx == 0)
                )
            )

        for opt in payload.options:
            self.db.add(QuestionOption(question_id=question.id, **opt.model_dump()))

        record_audit(
            self.db,
            actor=actor,
            action="question.create",
            resource_type="question",
            resource_id=str(question.id),
            details={"code": question.code, "is_scorable": question.is_scorable},
        )
        self.db.commit()
        return serialize_question(self.question_repo.get_by_id(question.id))  # type: ignore[arg-type]

    def add_question_to_card(
        self, card_id: UUID, payload: QuestionCreate, *, actor: ActorContext
    ) -> QuestionRead:
        if self.card_repo.get_by_id(card_id) is None:
            raise NotFoundError("QuestionCard", card_id)
        payload_with_card = payload.model_copy(update={"card_id": card_id})
        return self.create_question(payload_with_card, actor=actor)

    def list_questions(
        self,
        *,
        include_archived: bool = False,
        card_id: UUID | None = None,
        pillar_id: UUID | None = None,
        question_type: str | None = None,
        is_scorable: bool | None = None,
    ) -> list[QuestionRead]:
        questions = self.question_repo.list_questions(
            include_archived=include_archived,
            card_id=card_id,
            pillar_id=pillar_id,
            question_type=question_type,
            is_scorable=is_scorable,
        )
        return [serialize_question(q) for q in questions]

    def get_question(self, question_id: UUID) -> QuestionRead:
        q = self.question_repo.get_by_id(question_id)
        if q is None:
            raise NotFoundError("Question", question_id)
        return serialize_question(q)

    def update_question(
        self, question_id: UUID, payload: QuestionUpdate, *, actor: ActorContext
    ) -> QuestionRead:
        q = self.question_repo.get_by_id(question_id)
        if q is None:
            raise NotFoundError("Question", question_id)

        updates = payload.model_dump(exclude_unset=True)
        pillar_ids = updates.pop("pillar_ids", None)
        options = updates.pop("options", None)

        if "card_id" in updates and updates["card_id"] is not None:
            if self.card_repo.get_by_id(updates["card_id"]) is None:
                raise NotFoundError("QuestionCard", updates["card_id"])

        for field, value in updates.items():
            setattr(q, field, value.value if hasattr(value, "value") else value)

        if pillar_ids is not None:
            self._validate_pillar_ids(pillar_ids)
            q.pillar_mappings.clear()
            self.db.flush()
            for idx, pid in enumerate(dict.fromkeys(pillar_ids)):
                q.pillar_mappings.append(
                    QuestionPillarMapping(
                        question_id=q.id, pillar_id=pid, is_primary=(idx == 0)
                    )
                )

        if options is not None:
            q.options.clear()
            self.db.flush()
            for opt in options:
                q.options.append(QuestionOption(question_id=q.id, **opt))

        record_audit(
            self.db,
            actor=actor,
            action="question.update",
            resource_type="question",
            resource_id=str(q.id),
            details={"updated_fields": sorted(payload.model_dump(exclude_unset=True).keys())},
        )
        self.db.commit()
        return serialize_question(self.question_repo.get_by_id(q.id))  # type: ignore[arg-type]

    def archive_question(self, question_id: UUID, *, actor: ActorContext) -> QuestionRead:
        q = self.question_repo.get_by_id(question_id)
        if q is None:
            raise NotFoundError("Question", question_id)
        q.is_archived = True
        q.archived_at = datetime.now(timezone.utc)
        record_audit(
            self.db,
            actor=actor,
            action="question.archive",
            resource_type="question",
            resource_id=str(q.id),
        )
        self.db.commit()
        return serialize_question(self.question_repo.get_by_id(q.id))  # type: ignore[arg-type]

    # --- Questionnaires ---
    def _populate_questionnaire_structure(
        self,
        qn: Questionnaire,
        sections_in: list,
        questions_in: list,
    ) -> None:
        sections_by_code: dict[str, QuestionnaireSection] = {}
        linked_q_ids: set[UUID] = set()

        for sec in sections_in:
            section = QuestionnaireSection(
                questionnaire_id=qn.id,
                code=sec.code,
                title=sec.title,
                description=sec.description,
                display_order=sec.display_order,
            )
            self.db.add(section)
            self.db.flush()
            sections_by_code[sec.code] = section
            for idx, qid in enumerate(sec.question_ids):
                q = self.question_repo.get_by_id(qid)
                if q is None:
                    raise NotFoundError("Question", qid)
                if qid not in linked_q_ids:
                    self.db.add(
                        QuestionnaireQuestion(
                            questionnaire_id=qn.id,
                            section_id=section.id,
                            question_id=qid,
                            display_order=idx,
                        )
                    )
                    linked_q_ids.add(qid)

        for link in questions_in:
            q = self.question_repo.get_by_id(link.question_id)
            if q is None:
                raise NotFoundError("Question", link.question_id)
            if link.question_id in linked_q_ids:
                continue
            section_id = (
                sections_by_code[link.section_code].id
                if link.section_code and link.section_code in sections_by_code
                else None
            )
            self.db.add(
                QuestionnaireQuestion(
                    questionnaire_id=qn.id,
                    section_id=section_id,
                    question_id=link.question_id,
                    is_required_override=link.is_required_override,
                    display_order=link.display_order,
                )
            )
            linked_q_ids.add(link.question_id)

    def create_questionnaire(
        self, payload: QuestionnaireCreate, *, actor: ActorContext
    ) -> QuestionnaireRead:
        if self.questionnaire_repo.get_by_code(payload.code) is not None:
            raise ConflictError(
                f"Questionnaire with code '{payload.code}' already exists."
            )
        if payload.event_id is not None and self.event_repo.get_by_id(payload.event_id) is None:
            raise NotFoundError("Event", payload.event_id)

        qn = Questionnaire(
            event_id=payload.event_id,
            code=payload.code,
            title=payload.title,
            description=payload.description,
            questionnaire_type=payload.questionnaire_type.value,
            assessment_stage=payload.assessment_stage,
            version=payload.version,
            status=QuestionnaireStatus.DRAFT.value,
        )
        self.db.add(qn)
        self.db.flush()

        self._populate_questionnaire_structure(qn, payload.sections, payload.questions)

        record_audit(
            self.db,
            actor=actor,
            action="questionnaire.create",
            resource_type="questionnaire",
            resource_id=str(qn.id),
            details={"code": qn.code},
        )
        self.db.commit()
        return serialize_questionnaire(self.questionnaire_repo.get_by_id(qn.id))  # type: ignore[arg-type]

    def list_questionnaires(
        self,
        *,
        event_id: UUID | None = None,
        status: str | None = None,
        questionnaire_type: str | None = None,
    ) -> list[QuestionnaireRead]:
        items = self.questionnaire_repo.list_questionnaires(
            event_id=event_id, status=status, questionnaire_type=questionnaire_type
        )
        return [serialize_questionnaire(qn) for qn in items]

    def get_questionnaire(self, questionnaire_id: UUID) -> QuestionnaireRead:
        qn = self.questionnaire_repo.get_by_id(questionnaire_id)
        if qn is None:
            raise NotFoundError("Questionnaire", questionnaire_id)
        return serialize_questionnaire(qn)

    def update_questionnaire(
        self, questionnaire_id: UUID, payload: QuestionnaireUpdate, *, actor: ActorContext
    ) -> QuestionnaireRead:
        qn = self.questionnaire_repo.get_by_id(questionnaire_id)
        if qn is None:
            raise NotFoundError("Questionnaire", questionnaire_id)

        updates = payload.model_dump(exclude_unset=True)
        sections_in = updates.pop("sections", None)
        questions_in = updates.pop("questions", None)

        for field, value in updates.items():
            setattr(qn, field, value.value if hasattr(value, "value") else value)

        if sections_in is not None or questions_in is not None:
            qn.questionnaire_questions.clear()
            qn.sections.clear()
            self.db.flush()
            self._populate_questionnaire_structure(
                qn,
                payload.sections or [],
                payload.questions or [],
            )

        record_audit(
            self.db,
            actor=actor,
            action="questionnaire.update",
            resource_type="questionnaire",
            resource_id=str(qn.id),
        )
        self.db.commit()
        return serialize_questionnaire(self.questionnaire_repo.get_by_id(qn.id))  # type: ignore[arg-type]

    def publish_questionnaire(
        self, questionnaire_id: UUID, *, actor: ActorContext
    ) -> QuestionnaireRead:
        qn = self.questionnaire_repo.get_by_id(questionnaire_id)
        if qn is None:
            raise NotFoundError("Questionnaire", questionnaire_id)
        if not qn.questionnaire_questions:
            raise ValidationAppError(
                "Cannot publish an empty questionnaire. Attach at least one question first."
            )
        qn.status = QuestionnaireStatus.PUBLISHED.value
        qn.published_at = datetime.now(timezone.utc)
        record_audit(
            self.db,
            actor=actor,
            action="questionnaire.publish",
            resource_type="questionnaire",
            resource_id=str(qn.id),
        )
        self.db.commit()
        return serialize_questionnaire(self.questionnaire_repo.get_by_id(qn.id))  # type: ignore[arg-type]

    # --- Assessment Submission ---
    @staticmethod
    def _validate_response_against_question(
        question: Question, resp: AssessmentResponseIn
    ) -> bool:
        """Validate response data matches question type. Returns True if answered."""
        qtype = question.question_type
        if qtype in {QuestionType.SHORT_TEXT.value, QuestionType.LONG_TEXT.value}:
            return bool(resp.response_text and resp.response_text.strip())
        if qtype == QuestionType.EMAIL.value:
            if not (resp.response_text and resp.response_text.strip()):
                return False
            normalise_email(resp.response_text)
            return True
        if qtype == QuestionType.PHONE.value:
            if not (resp.response_text and resp.response_text.strip()):
                return False
            normalise_phone(resp.response_text)
            return True
        if qtype == QuestionType.YES_NO.value:
            return resp.response_boolean is not None
        if qtype in {QuestionType.RATING_SCALE.value, QuestionType.NUMERIC.value}:
            if resp.response_numeric is None:
                return False
            cfg = question.validation_config or {}
            if "min" in cfg and resp.response_numeric < float(cfg["min"]):
                raise ValidationAppError(
                    f"Response for question '{question.code}' is below minimum {cfg['min']}."
                )
            if "max" in cfg and resp.response_numeric > float(cfg["max"]):
                raise ValidationAppError(
                    f"Response for question '{question.code}' exceeds maximum {cfg['max']}."
                )
            return True
        if qtype == QuestionType.DATE.value:
            return resp.response_date is not None
        if qtype == QuestionType.SINGLE_CHOICE.value:
            val = resp.response_text
            if not val:
                return False
            valid_vals = {o.option_value for o in question.options if o.is_active}
            if valid_vals and val not in valid_vals:
                raise ValidationAppError(
                    f"Invalid option '{val}' for single-choice question '{question.code}'."
                )
            return True
        if qtype == QuestionType.MULTIPLE_CHOICE.value:
            vals = resp.response_json
            if not vals:
                return False
            if not isinstance(vals, list):
                raise ValidationAppError(
                    f"Multiple-choice question '{question.code}' expects a list in response_json."
                )
            valid_vals = {o.option_value for o in question.options if o.is_active}
            if valid_vals:
                invalid = [v for v in vals if v not in valid_vals]
                if invalid:
                    raise ValidationAppError(
                        f"Invalid options {invalid} for question '{question.code}'."
                    )
            return len(vals) > 0
        return False

    def submit_assessment(
        self, payload: AssessmentSubmitRequest, *, actor: ActorContext
    ) -> AssessmentSubmission:
        event = self.event_repo.get_by_id(payload.event_id)
        if event is None:
            raise NotFoundError("Event", payload.event_id)

        qn = self.questionnaire_repo.get_by_id(payload.questionnaire_id)
        if qn is None:
            raise NotFoundError("Questionnaire", payload.questionnaire_id)
        if qn.status != QuestionnaireStatus.PUBLISHED.value:
            raise ValidationAppError(
                "Assessments can only be submitted against a published questionnaire."
            )

        # Validate ALL responses before creating/flushing any database records (atomic validation)
        qn_links = {link.question_id: link for link in qn.questionnaire_questions}
        answered_ids: set[UUID] = set()
        seen_q_ids: set[UUID] = set()
        validated_pairs: list[tuple[Question, AssessmentResponseIn]] = []

        for resp_in in payload.responses:
            if resp_in.question_id in seen_q_ids:
                raise ValidationAppError(
                    f"Duplicate response submitted for question '{resp_in.question_id}'."
                )
            seen_q_ids.add(resp_in.question_id)

            link = qn_links.get(resp_in.question_id)
            question = link.question if link else self.question_repo.get_by_id(resp_in.question_id)
            if question is None:
                raise NotFoundError("Question", resp_in.question_id)

            is_answered = self._validate_response_against_question(question, resp_in)
            if is_answered and resp_in.question_id in qn_links:
                answered_ids.add(resp_in.question_id)
            validated_pairs.append((question, resp_in))

        # Enforce required questions defined on the questionnaire
        missing_required = []
        for qid, link in qn_links.items():
            req = (
                link.is_required_override
                if link.is_required_override is not None
                else link.question.is_required
            )
            if req and qid not in answered_ids:
                missing_required.append(link.question.code)
        if missing_required:
            raise ValidationAppError(
                "One or more required questionnaire questions were not answered.",
                details={"missing_question_codes": missing_required},
            )

        # Extract fallback profile fields from Section A responses (when present)
        resp_by_code = {q.code: (q, r) for q, r in validated_pairs}

        def _text_for(code: str) -> str | None:
            pair = resp_by_code.get(code)
            if not pair:
                return None
            val = pair[1].response_text
            return val.strip() if val and val.strip() else None

        def _industry_from_section_a() -> str | None:
            pair = resp_by_code.get("a5_industry_sector")
            if not pair:
                return None
            q_obj, r_obj = pair
            if r_obj.response_text == "other" and r_obj.explanation_text and r_obj.explanation_text.strip():
                return r_obj.explanation_text.strip()
            if r_obj.response_text:
                label = next(
                    (o.option_label for o in q_obj.options if o.option_value == r_obj.response_text),
                    r_obj.response_text,
                )
                return label
            return None

        _yoe_bracket_map = {
            "less_than_1_year": 0,
            "1_2_years": 2,
            "3_5_years": 4,
            "6_10_years": 8,
            "more_than_10_years": 12,
        }

        # Identify or auto-register participant via participant_id, phone, or email
        now = datetime.now(timezone.utc)
        participant = None
        if payload.participant_id is not None:
            participant = self.participant_repo.get_by_id(payload.participant_id)
            if participant is None:
                raise NotFoundError("Participant", payload.participant_id)
        else:
            raw_phone = payload.phone or _text_for("a3_active_phone_number")
            raw_email = payload.email or _text_for("a2_email_address")
            phone_norm = normalise_phone(raw_phone) if raw_phone else None
            email_norm = normalise_email(raw_email) if raw_email else None
            participant, _ = self.participant_repo.find_by_contact(
                phone_normalised=phone_norm, email_normalised=email_norm
            )

            if participant is None:
                if not phone_norm and not email_norm:
                    raise ValidationAppError(
                        "Provide a valid phone number or email address to register and submit."
                    )
                pu = payload.profile_updates
                inferred_name = (
                    (payload.full_name.strip() if payload.full_name and payload.full_name.strip() else None)
                    or (pu.full_name.strip() if pu and pu.full_name and pu.full_name.strip() else None)
                    or _text_for("a1_full_name")
                    or (email_norm.split("@")[0] if email_norm else None)
                    or "CCI STEM Participant"
                )
                inferred_role = (pu.current_role if pu and pu.current_role else None) or _text_for("a4_current_professional_role")
                inferred_industry = (pu.industry if pu and pu.industry else None) or _industry_from_section_a()
                inferred_org = (pu.organisation if pu and pu.organisation else None) or _text_for("a6_organisation")
                inferred_reason = (pu.reason_for_attending if pu and pu.reason_for_attending else None) or _text_for("a8_motivation_to_attend")
                inferred_yoe = (
                    pu.years_of_experience
                    if pu and pu.years_of_experience is not None
                    else _yoe_bracket_map.get(_text_for("a7_years_of_experience") or "")
                )
                consent = bool(pu.consent_given) if pu and pu.consent_given is not None else True

                participant = Participant(
                    full_name=inferred_name,
                    email_raw=raw_email.strip() if raw_email else None,
                    email_normalised=email_norm,
                    phone_raw=raw_phone.strip() if raw_phone else None,
                    phone_normalised=phone_norm,
                    current_role=inferred_role,
                    industry=inferred_industry,
                    organisation=inferred_org,
                    years_of_experience=inferred_yoe,
                    reason_for_attending=inferred_reason,
                    data_source="self_assessment",
                    consent_given=consent,
                    consent_recorded_at=now if consent else None,
                )
                self.participant_repo.create(participant)
                record_audit(
                    self.db,
                    actor=actor,
                    action="participant.auto_register",
                    resource_type="participant",
                    resource_id=str(participant.id),
                    details={"event_id": str(event.id), "channel": payload.submission_channel},
                )
            else:
                # Safely enrich missing secondary contact if not owned by another participant
                if not participant.email_normalised and email_norm:
                    if self.participant_repo.get_by_email(email_norm) is None:
                        participant.email_raw = raw_email.strip() if raw_email else None
                        participant.email_normalised = email_norm
                if not participant.phone_normalised and phone_norm:
                    if self.participant_repo.get_by_phone(phone_norm) is None:
                        participant.phone_raw = raw_phone.strip() if raw_phone else None
                        participant.phone_normalised = phone_norm

        total_questions = len(qn_links)
        completeness_ratio = (
            round(len(answered_ids) / total_questions, 4) if total_questions > 0 else 0.0
        )

        # Optional Section A background updates (applied only after validation passes)
        if payload.profile_updates is not None:
            p_updates = payload.profile_updates.model_dump(exclude_unset=True)
            for field, val in p_updates.items():
                if val is not None:
                    setattr(participant, field, val)
            if p_updates.get("consent_given") is True and not participant.consent_recorded_at:
                participant.consent_recorded_at = now

        # Ensure participant is registered for this event automatically
        if self.event_repo.get_registration(event.id, participant.id) is None:
            self.db.add(
                EventRegistration(
                    event_id=event.id,
                    participant_id=participant.id,
                    registration_source=RegistrationSource.FORM.value,
                    registration_status=RegistrationStatus.REGISTERED.value,
                    reason_for_attending=participant.reason_for_attending,
                )
            )

        submission = AssessmentSubmission(
            participant_id=participant.id,
            event_id=event.id,
            questionnaire_id=qn.id,
            submission_channel=payload.submission_channel,
            status=SubmissionStatus.SUBMITTED.value,
            started_at=payload.started_at,
            submitted_at=datetime.now(timezone.utc),
            completeness_ratio=completeness_ratio,
            metadata_json=payload.metadata_json,
        )
        self.db.add(submission)
        self.db.flush()

        for question, resp_in in validated_pairs:
            self.db.add(
                AssessmentResponse(
                    submission_id=submission.id,
                    question_id=question.id,
                    response_text=resp_in.response_text,
                    response_numeric=resp_in.response_numeric,
                    response_boolean=resp_in.response_boolean,
                    response_date=resp_in.response_date,
                    response_json=resp_in.response_json,
                    explanation_text=resp_in.explanation_text,
                )
            )

        record_audit(
            self.db,
            actor=actor,
            action="assessment.submit",
            resource_type="assessment_submission",
            resource_id=str(submission.id),
            details={
                "participant_id": str(participant.id),
                "event_id": str(event.id),
                "completeness_ratio": submission.completeness_ratio,
            },
        )
        self.db.commit()
        return self.assessment_repo.get_by_id(submission.id)  # type: ignore[return-value]

    def get_assessment(self, assessment_id: UUID) -> AssessmentSubmission:
        sub = self.assessment_repo.get_by_id(assessment_id)
        if sub is None:
            raise NotFoundError("AssessmentSubmission", assessment_id)
        return sub

    def list_participant_assessments(
        self, participant_id: UUID, *, event_id: UUID | None = None
    ) -> list[AssessmentSubmission]:
        if self.participant_repo.get_by_id(participant_id) is None:
            raise NotFoundError("Participant", participant_id)
        return self.assessment_repo.list_by_participant(participant_id, event_id=event_id)

    def list_assessments(
        self,
        *,
        event_id: UUID | None = None,
        questionnaire_id: UUID | None = None,
        participant_id: UUID | None = None,
        status: str | None = None,
        q: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        sort_order: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AssessmentSummaryRead], int]:
        stmt = (
            select(AssessmentSubmission, Participant, Event, Questionnaire)
            .join(Participant, Participant.id == AssessmentSubmission.participant_id)
            .join(Event, Event.id == AssessmentSubmission.event_id)
            .join(Questionnaire, Questionnaire.id == AssessmentSubmission.questionnaire_id)
        )
        count_stmt = (
            select(func.count(AssessmentSubmission.id))
            .join(Participant, Participant.id == AssessmentSubmission.participant_id)
            .join(Event, Event.id == AssessmentSubmission.event_id)
            .join(Questionnaire, Questionnaire.id == AssessmentSubmission.questionnaire_id)
        )

        if event_id is not None:
            stmt = stmt.where(AssessmentSubmission.event_id == event_id)
            count_stmt = count_stmt.where(AssessmentSubmission.event_id == event_id)
        if questionnaire_id is not None:
            stmt = stmt.where(AssessmentSubmission.questionnaire_id == questionnaire_id)
            count_stmt = count_stmt.where(
                AssessmentSubmission.questionnaire_id == questionnaire_id
            )
        if participant_id is not None:
            stmt = stmt.where(AssessmentSubmission.participant_id == participant_id)
            count_stmt = count_stmt.where(
                AssessmentSubmission.participant_id == participant_id
            )
        if status is not None:
            stmt = stmt.where(AssessmentSubmission.status == status)
            count_stmt = count_stmt.where(AssessmentSubmission.status == status)
        if q and q.strip():
            term = f"%{q.strip()}%"
            search_filter = or_(
                Participant.full_name.ilike(term),
                Participant.email_normalised.ilike(term),
                Participant.phone_normalised.ilike(term),
            )
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)
        if date_from is not None:
            start_dt = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
            stmt = stmt.where(AssessmentSubmission.submitted_at >= start_dt)
            count_stmt = count_stmt.where(AssessmentSubmission.submitted_at >= start_dt)
        if date_to is not None:
            end_dt = datetime.combine(date_to, time.max, tzinfo=timezone.utc)
            stmt = stmt.where(AssessmentSubmission.submitted_at <= end_dt)
            count_stmt = count_stmt.where(AssessmentSubmission.submitted_at <= end_dt)

        total = int(self.db.execute(count_stmt).scalar_one())
        order_expr = (
            AssessmentSubmission.submitted_at.asc()
            if sort_order.lower() == "asc"
            else AssessmentSubmission.submitted_at.desc()
        )
        rows = self.db.execute(stmt.order_by(order_expr).limit(limit).offset(offset)).all()
        if not rows:
            return [], total

        sub_ids = [r[0].id for r in rows]
        resp_counts = dict(
            self.db.execute(
                select(AssessmentResponse.submission_id, func.count(AssessmentResponse.id))
                .where(AssessmentResponse.submission_id.in_(sub_ids))
                .group_by(AssessmentResponse.submission_id)
            ).all()
        )

        items = [
            AssessmentSummaryRead(
                id=sub.id,
                participant_id=sub.participant_id,
                participant_name=participant.full_name,
                participant_email=participant.email_normalised,
                participant_phone=participant.phone_normalised,
                event_id=sub.event_id,
                event_title=event.title,
                questionnaire_id=sub.questionnaire_id,
                questionnaire_title=qn.title,
                questionnaire_type=qn.questionnaire_type,
                submission_channel=sub.submission_channel,
                status=sub.status,
                started_at=sub.started_at,
                submitted_at=sub.submitted_at,
                completeness_ratio=sub.completeness_ratio,
                responses_count=int(resp_counts.get(sub.id, 0)),
                created_at=sub.created_at,
            )
            for sub, participant, event, qn in rows
        ]
        return items, total

    def list_feedback(
        self,
        *,
        event_id: UUID | None = None,
        questionnaire_id: UUID | None = None,
        question_id: UUID | None = None,
        card_id: UUID | None = None,
        section_code: str | None = None,
        pillar_id: UUID | None = None,
        is_scorable: bool | None = None,
        industry: str | None = None,
        participant_id: UUID | None = None,
        q: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[FeedbackResponseRead], int]:
        stmt = (
            select(
                AssessmentResponse,
                AssessmentSubmission,
                Participant,
                Event,
                Questionnaire,
                Question,
                QuestionnaireSection,
            )
            .join(
                AssessmentSubmission,
                AssessmentSubmission.id == AssessmentResponse.submission_id,
            )
            .join(Participant, Participant.id == AssessmentSubmission.participant_id)
            .join(Event, Event.id == AssessmentSubmission.event_id)
            .join(Questionnaire, Questionnaire.id == AssessmentSubmission.questionnaire_id)
            .join(Question, Question.id == AssessmentResponse.question_id)
            .outerjoin(
                QuestionnaireQuestion,
                (QuestionnaireQuestion.questionnaire_id == AssessmentSubmission.questionnaire_id)
                & (QuestionnaireQuestion.question_id == AssessmentResponse.question_id),
            )
            .outerjoin(
                QuestionnaireSection,
                QuestionnaireSection.id == QuestionnaireQuestion.section_id,
            )
            .options(selectinload(Question.pillar_mappings))
        )
        count_stmt = (
            select(func.count(func.distinct(AssessmentResponse.id)))
            .join(
                AssessmentSubmission,
                AssessmentSubmission.id == AssessmentResponse.submission_id,
            )
            .join(Participant, Participant.id == AssessmentSubmission.participant_id)
            .join(Event, Event.id == AssessmentSubmission.event_id)
            .join(Questionnaire, Questionnaire.id == AssessmentSubmission.questionnaire_id)
            .join(Question, Question.id == AssessmentResponse.question_id)
            .outerjoin(
                QuestionnaireQuestion,
                (QuestionnaireQuestion.questionnaire_id == AssessmentSubmission.questionnaire_id)
                & (QuestionnaireQuestion.question_id == AssessmentResponse.question_id),
            )
            .outerjoin(
                QuestionnaireSection,
                QuestionnaireSection.id == QuestionnaireQuestion.section_id,
            )
        )

        if event_id is not None:
            stmt = stmt.where(AssessmentSubmission.event_id == event_id)
            count_stmt = count_stmt.where(AssessmentSubmission.event_id == event_id)
        if questionnaire_id is not None:
            stmt = stmt.where(AssessmentSubmission.questionnaire_id == questionnaire_id)
            count_stmt = count_stmt.where(
                AssessmentSubmission.questionnaire_id == questionnaire_id
            )
        if question_id is not None:
            stmt = stmt.where(AssessmentResponse.question_id == question_id)
            count_stmt = count_stmt.where(AssessmentResponse.question_id == question_id)
        if card_id is not None:
            stmt = stmt.where(Question.card_id == card_id)
            count_stmt = count_stmt.where(Question.card_id == card_id)
        if section_code is not None:
            stmt = stmt.where(QuestionnaireSection.code == section_code)
            count_stmt = count_stmt.where(QuestionnaireSection.code == section_code)
        if pillar_id is not None:
            pillar_q_subq = select(QuestionPillarMapping.question_id).where(
                QuestionPillarMapping.pillar_id == pillar_id
            )
            stmt = stmt.where(Question.id.in_(pillar_q_subq))
            count_stmt = count_stmt.where(Question.id.in_(pillar_q_subq))
        if is_scorable is not None:
            stmt = stmt.where(Question.is_scorable.is_(is_scorable))
            count_stmt = count_stmt.where(Question.is_scorable.is_(is_scorable))
        if industry and industry.strip():
            ind_filter = Participant.industry.ilike(f"%{industry.strip()}%")
            stmt = stmt.where(ind_filter)
            count_stmt = count_stmt.where(ind_filter)
        if participant_id is not None:
            stmt = stmt.where(AssessmentSubmission.participant_id == participant_id)
            count_stmt = count_stmt.where(
                AssessmentSubmission.participant_id == participant_id
            )
        if q and q.strip():
            term = f"%{q.strip()}%"
            text_filter = or_(
                AssessmentResponse.response_text.ilike(term),
                AssessmentResponse.explanation_text.ilike(term),
            )
            stmt = stmt.where(text_filter)
            count_stmt = count_stmt.where(text_filter)
        if date_from is not None:
            start_dt = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
            stmt = stmt.where(AssessmentSubmission.submitted_at >= start_dt)
            count_stmt = count_stmt.where(AssessmentSubmission.submitted_at >= start_dt)
        if date_to is not None:
            end_dt = datetime.combine(date_to, time.max, tzinfo=timezone.utc)
            stmt = stmt.where(AssessmentSubmission.submitted_at <= end_dt)
            count_stmt = count_stmt.where(AssessmentSubmission.submitted_at <= end_dt)

        total = int(self.db.execute(count_stmt).scalar_one())
        rows = (
            self.db.execute(
                stmt.order_by(
                    AssessmentSubmission.submitted_at.desc(),
                    AssessmentResponse.answered_at.desc(),
                )
                .limit(limit)
                .offset(offset)
            )
            .unique()
            .all()
        )

        items = [
            FeedbackResponseRead(
                response_id=resp.id,
                submission_id=sub.id,
                submitted_at=sub.submitted_at,
                answered_at=resp.answered_at,
                event_id=sub.event_id,
                event_title=event.title,
                questionnaire_id=sub.questionnaire_id,
                questionnaire_title=qn.title,
                participant_id=sub.participant_id,
                participant_name=participant.full_name,
                participant_industry=participant.industry,
                participant_role=participant.current_role,
                question_id=question.id,
                question_code=question.code,
                question_text=question.question_text,
                question_type=question.question_type,
                is_scorable=question.is_scorable,
                card_id=question.card_id,
                section_code=section.code if section else None,
                section_title=section.title if section else None,
                pillar_ids=[m.pillar_id for m in question.pillar_mappings],
                response_text=resp.response_text,
                response_numeric=resp.response_numeric,
                response_boolean=resp.response_boolean,
                response_date=resp.response_date,
                response_json=resp.response_json,
                explanation_text=resp.explanation_text,
            )
            for resp, sub, participant, event, qn, question, section in rows
        ]
        return items, total
