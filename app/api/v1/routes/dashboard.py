from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.question import AIQuestion, AIQuestionStatus
from app.models.record import DailyRecord, RecordStatus
from app.models.user import User, UserRole
from app.schemas.dashboard import DashboardRecordRow, DashboardResponse

router = APIRouter(prefix="/dashboard", tags=["대시보드"])


def _require_doctor(current_user: User) -> None:
	if current_user.role != UserRole.doctor:
		raise HTTPException(
			status_code=status.HTTP_403_FORBIDDEN,
			detail="의사만 접근할 수 있습니다.",
		)


@router.get(
	"",
	response_model=DashboardResponse,
	summary="의사 대시보드",
	description="오늘 제출된 환자 기록 목록과 통계를 반환합니다.",
)
def get_dashboard(
	db: Session = Depends(get_db),
	current_user: User = Depends(get_current_user),
) -> DashboardResponse:
	_require_doctor(current_user)

	today = date.today()

	# ── 오늘 제출된 기록 목록 (환자 정보 JOIN) ─────────────────
	today_records: List[tuple] = (
		db.query(DailyRecord, User)
		.join(User, DailyRecord.patient_id == User.id)
		.filter(DailyRecord.record_date == today)
		.order_by(DailyRecord.submitted_at.desc())
		.all()
	)

	# ── 전체 활성 환자 수 ──────────────────────────────────────
	total_patients: int = (
		db.query(User)
		.filter(User.role == UserRole.patient, User.is_active == True)
		.count()
	)

	# ── 미검토 AI 질문 수 — record_id별로 한 번에 집계 ─────────
	record_ids = [rec.id for rec, _ in today_records]
	ai_counts: dict[int, int] = {}
	if record_ids:
		rows = (
			db.query(
				AIQuestion.daily_record_id,
				func.count(AIQuestion.id).label("cnt"),
			)
			.filter(
				AIQuestion.daily_record_id.in_(record_ids),
				AIQuestion.status == AIQuestionStatus.pending,
			)
			.group_by(AIQuestion.daily_record_id)
			.all()
		)
		ai_counts = {row.daily_record_id: row.cnt for row in rows}

	# ── 통계 계산 ─────────────────────────────────────────────
	total_submitted = len(today_records)
	pending_count   = sum(1 for rec, _ in today_records if rec.status == RecordStatus.submitted)
	approved_count  = sum(1 for rec, _ in today_records if rec.status == RecordStatus.reviewed)

	# ── 기록 행 조립 ──────────────────────────────────────────
	records_out = [
		DashboardRecordRow(
			record_id           = rec.id,
			patient_id          = rec.patient_id,
			patient_name        = patient.name,
			submitted_at        = rec.submitted_at.isoformat() if rec.submitted_at else None,
			status              = rec.status.value,
			unreviewed_ai_count = ai_counts.get(rec.id, 0),
		)
		for rec, patient in today_records
	]

	return DashboardResponse(
		today           = today.isoformat(),
		total_submitted = total_submitted,
		pending_count   = pending_count,
		approved_count  = approved_count,
		total_patients  = total_patients,
		records         = records_out,
	)
