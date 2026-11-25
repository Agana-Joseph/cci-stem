"""Report generation and JSON/CSV/XLSX export service."""

import json
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import UUID

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.service import AnalyticsService
from app.core.config import get_settings
from app.core.enums import ExportFormat
from app.core.exceptions import NotFoundError
from app.core.security import ActorContext
from app.models.admin import ReportRecord
from app.repositories.participant import EventRepository, ParticipantRepository
from app.scoring.service import ScoringService
from app.services.audit_service import record_audit
from app.services.impact_service import ImpactTrackingService


class ReportingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.analytics = AnalyticsService(db)
        self.event_repo = EventRepository(db)
        self.participant_repo = ParticipantRepository(db)
        self.scoring = ScoringService(db)
        self.impact = ImpactTrackingService(db)

    def build_event_report(self, event_id: UUID) -> dict[str, Any]:
        event = self.event_repo.get_by_id(event_id)
        if event is None:
            raise NotFoundError("Event", event_id)

        overview = self.analytics.get_event_overview(event_id)
        pillars = self.analytics.get_pillar_analytics(event_id)
        networking = self.analytics.get_networking_analytics(event_id)
        application = self.analytics.get_application_analytics(event_id)
        follow_ups = self.analytics.get_follow_up_analytics(event_id)

        return {
            "report_type": "event_summary",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "event": {
                "id": str(event.id),
                "slug": event.slug,
                "title": event.title,
                "event_date": event.event_date.isoformat(),
                "location": event.location,
                "status": event.status,
            },
            "overview": overview,
            "pillars": pillars["pillars"],
            "networking": networking,
            "application": application,
            "follow_ups": follow_ups["stages"],
        }

    def build_participant_report(
        self, participant_id: UUID, *, event_id: UUID | None = None
    ) -> dict[str, Any]:
        participant = self.participant_repo.get_by_id(participant_id)
        if participant is None:
            raise NotFoundError("Participant", participant_id)

        impact_summary = self.impact.get_participant_impact_summary(
            participant_id, event_id=event_id
        )
        score_history = self.scoring.get_participant_scores(
            participant_id, event_id=event_id, latest_only=False
        )

        return {
            "report_type": "participant_impact",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "participant": {
                "id": str(participant.id),
                "full_name": participant.full_name,
                "current_role": participant.current_role,
                "industry": participant.industry,
                "organisation": participant.organisation,
                "years_of_experience": participant.years_of_experience,
            },
            "impact_summary": impact_summary.model_dump(mode="json"),
            "score_history": [s.model_dump(mode="json") for s in score_history],
        }

    def _write_export_file(
        self,
        *,
        prefix: str,
        export_format: ExportFormat,
        report_payload: dict[str, Any],
        tabular_rows: list[dict[str, Any]],
    ) -> Path:
        settings = get_settings()
        storage_dir = Path(settings.reports_storage_dir)
        storage_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        file_path = storage_dir / f"{prefix}_{ts}.{export_format.value}"

        if export_format == ExportFormat.JSON:
            file_path.write_text(
                json.dumps(report_payload, indent=2, default=str), encoding="utf-8"
            )
        elif export_format == ExportFormat.CSV:
            df = pd.DataFrame(tabular_rows or [{"note": "No tabular records available"}])
            df.to_csv(file_path, index=False)
        elif export_format == ExportFormat.XLSX:
            df = pd.DataFrame(tabular_rows or [{"note": "No tabular records available"}])
            with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="Summary", index=False)

        return file_path

    def export_event_report(
        self,
        event_id: UUID,
        *,
        export_format: ExportFormat = ExportFormat.JSON,
        actor: ActorContext,
    ) -> dict[str, Any]:
        report = self.build_event_report(event_id)
        tabular_rows = [
            {
                "pillar_code": p["pillar_code"],
                "pillar_name": p["pillar_name"],
                "default_weight": p["default_weight"],
                "average_score": p["average"],
                "median_score": p["median"],
                "response_count": p["response_count"],
                "coverage_ratio": p["data_coverage"]["coverage_ratio"],
                "coverage_level": p["data_coverage"]["coverage_level"],
            }
            for p in report["pillars"]
        ]

        file_path = self._write_export_file(
            prefix=f"event_report_{event_id}",
            export_format=export_format,
            report_payload=report,
            tabular_rows=tabular_rows,
        )

        record = ReportRecord(
            report_type="event_summary",
            event_id=event_id,
            export_format=export_format.value,
            generated_by=actor.actor_id,
            file_path=str(file_path),
            parameters_json={"export_format": export_format.value},
            summary_json={"event_title": report["event"]["title"]},
        )
        self.db.add(record)
        self.db.flush()
        record_audit(
            self.db,
            actor=actor,
            action="report.export_event",
            resource_type="report_record",
            resource_id=str(record.id),
            details={"event_id": str(event_id), "format": export_format.value},
        )
        self.db.commit()
        self.db.refresh(record)

        return {
            "report_record_id": str(record.id),
            "report_type": record.report_type,
            "export_format": record.export_format,
            "file_path": record.file_path,
            "generated_at": record.generated_at.isoformat(),
            "report": report,
        }

    def export_participant_report(
        self,
        participant_id: UUID,
        *,
        event_id: UUID | None = None,
        export_format: ExportFormat = ExportFormat.JSON,
        actor: ActorContext,
    ) -> dict[str, Any]:
        report = self.build_participant_report(participant_id, event_id=event_id)
        tabular_rows = []
        for s in report["score_history"]:
            tabular_rows.append(
                {
                    "score_id": s["id"],
                    "event_id": s["event_id"],
                    "framework_version": s["framework_version"],
                    "status": s["status"],
                    "overall_impact_score": s["overall_impact_score"],
                    "immediate_impact_score": s["immediate_impact_score"],
                    "post_event_application_score": s["post_event_application_score"],
                    "sustained_impact_score": s["sustained_impact_score"],
                    "completeness_ratio": s["completeness_ratio"],
                    "is_latest": s["is_latest"],
                    "calculated_at": s["calculated_at"],
                }
            )

        file_path = self._write_export_file(
            prefix=f"participant_report_{participant_id}",
            export_format=export_format,
            report_payload=report,
            tabular_rows=tabular_rows,
        )

        record = ReportRecord(
            report_type="participant_impact",
            event_id=event_id,
            participant_id=participant_id,
            export_format=export_format.value,
            generated_by=actor.actor_id,
            file_path=str(file_path),
            parameters_json={
                "export_format": export_format.value,
                "event_id": str(event_id) if event_id else None,
            },
            summary_json={"participant_name": report["participant"]["full_name"]},
        )
        self.db.add(record)
        self.db.flush()
        record_audit(
            self.db,
            actor=actor,
            action="report.export_participant",
            resource_type="report_record",
            resource_id=str(record.id),
            details={"participant_id": str(participant_id), "format": export_format.value},
        )
        self.db.commit()
        self.db.refresh(record)

        return {
            "report_record_id": str(record.id),
            "report_type": record.report_type,
            "export_format": record.export_format,
            "file_path": record.file_path,
            "generated_at": record.generated_at.isoformat(),
            "report": report,
        }

    def list_report_records(
        self,
        *,
        event_id: UUID | None = None,
        participant_id: UUID | None = None,
        report_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        stmt = select(ReportRecord)
        count_stmt = select(func.count(ReportRecord.id))
        if event_id is not None:
            stmt = stmt.where(ReportRecord.event_id == event_id)
            count_stmt = count_stmt.where(ReportRecord.event_id == event_id)
        if participant_id is not None:
            stmt = stmt.where(ReportRecord.participant_id == participant_id)
            count_stmt = count_stmt.where(ReportRecord.participant_id == participant_id)
        if report_type is not None:
            stmt = stmt.where(ReportRecord.report_type == report_type)
            count_stmt = count_stmt.where(ReportRecord.report_type == report_type)

        total = int(self.db.execute(count_stmt).scalar_one())
        records = list(
            self.db.execute(
                stmt.order_by(ReportRecord.generated_at.desc()).limit(limit).offset(offset)
            )
            .scalars()
            .all()
        )
        items = [
            {
                "id": str(r.id),
                "report_type": r.report_type,
                "event_id": str(r.event_id) if r.event_id else None,
                "participant_id": str(r.participant_id) if r.participant_id else None,
                "export_format": r.export_format,
                "generated_by": r.generated_by,
                "file_path": r.file_path,
                "parameters_json": r.parameters_json,
                "summary_json": r.summary_json,
                "generated_at": r.generated_at.isoformat(),
            }
            for r in records
        ]
        return items, total

    @staticmethod
    def _serialize_download_bytes(
        *,
        export_format: ExportFormat,
        report_payload: dict[str, Any],
        tabular_rows: list[dict[str, Any]],
    ) -> tuple[bytes, str]:
        if export_format == ExportFormat.JSON:
            content = json.dumps(report_payload, indent=2, default=str).encode("utf-8")
            return content, "application/json"
        if export_format == ExportFormat.CSV:
            df = pd.DataFrame(tabular_rows or [{"note": "No tabular records available"}])
            return df.to_csv(index=False).encode("utf-8"), "text/csv; charset=utf-8"
        df = pd.DataFrame(tabular_rows or [{"note": "No tabular records available"}])
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Summary", index=False)
        return (
            buf.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def render_event_report_download(
        self,
        event_id: UUID,
        *,
        export_format: ExportFormat = ExportFormat.CSV,
        actor: ActorContext,
    ) -> tuple[bytes, str, str]:
        report = self.build_event_report(event_id)
        tabular_rows = [
            {
                "pillar_code": p["pillar_code"],
                "pillar_name": p["pillar_name"],
                "default_weight": p["default_weight"],
                "average_score": p["average"],
                "median_score": p["median"],
                "response_count": p["response_count"],
                "coverage_ratio": p["data_coverage"]["coverage_ratio"],
                "coverage_level": p["data_coverage"]["coverage_level"],
            }
            for p in report["pillars"]
        ]
        content, media_type = self._serialize_download_bytes(
            export_format=export_format,
            report_payload=report,
            tabular_rows=tabular_rows,
        )
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"event_report_{report['event']['slug']}_{ts}.{export_format.value}"
        record = ReportRecord(
            report_type="event_summary",
            event_id=event_id,
            export_format=export_format.value,
            generated_by=actor.actor_id,
            file_path=None,
            parameters_json={"export_format": export_format.value, "delivery": "stream"},
            summary_json={"event_title": report["event"]["title"]},
        )
        self.db.add(record)
        self.db.flush()
        record_audit(
            self.db,
            actor=actor,
            action="report.download_event",
            resource_type="report_record",
            resource_id=str(record.id),
            details={"event_id": str(event_id), "format": export_format.value},
        )
        self.db.commit()
        return content, media_type, filename

    def render_participant_report_download(
        self,
        participant_id: UUID,
        *,
        event_id: UUID | None = None,
        export_format: ExportFormat = ExportFormat.CSV,
        actor: ActorContext,
    ) -> tuple[bytes, str, str]:
        report = self.build_participant_report(participant_id, event_id=event_id)
        tabular_rows = [
            {
                "score_id": s["id"],
                "event_id": s["event_id"],
                "framework_version": s["framework_version"],
                "status": s["status"],
                "overall_impact_score": s["overall_impact_score"],
                "immediate_impact_score": s["immediate_impact_score"],
                "post_event_application_score": s["post_event_application_score"],
                "sustained_impact_score": s["sustained_impact_score"],
                "completeness_ratio": s["completeness_ratio"],
                "is_latest": s["is_latest"],
                "calculated_at": s["calculated_at"],
            }
            for s in report["score_history"]
        ]
        content, media_type = self._serialize_download_bytes(
            export_format=export_format,
            report_payload=report,
            tabular_rows=tabular_rows,
        )
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"participant_report_{participant_id}_{ts}.{export_format.value}"
        record = ReportRecord(
            report_type="participant_impact",
            event_id=event_id,
            participant_id=participant_id,
            export_format=export_format.value,
            generated_by=actor.actor_id,
            file_path=None,
            parameters_json={
                "export_format": export_format.value,
                "event_id": str(event_id) if event_id else None,
                "delivery": "stream",
            },
            summary_json={"participant_name": report["participant"]["full_name"]},
        )
        self.db.add(record)
        self.db.flush()
        record_audit(
            self.db,
            actor=actor,
            action="report.download_participant",
            resource_type="report_record",
            resource_id=str(record.id),
            details={"participant_id": str(participant_id), "format": export_format.value},
        )
        self.db.commit()
        return content, media_type, filename
