"""
특정 환자의 '오늘' 일일 기록 1건을 통째로 삭제하는 일회성 스크립트.
daily_records 와 연결된 survey_responses / ai_questions / exchange_records 까지 함께 삭제한다.

데모 재시연 등을 위해 오늘 제출한 기록을 미제출(=기록 없음) 상태로 되돌릴 때 사용.

환경변수:
  PATIENT_NAME  대상 환자 이름   (기본값: 박차원)
  RECORD_DATE   대상 날짜 YYYY-MM-DD (기본값: 오늘, Asia/Seoul 기준)
  CONFIRM       'yes' 일 때만 실제 삭제. 아니면 미리보기(dry-run)만.

실행 (Cloud Run Job):
  먼저 미리보기 → 확인 후 CONFIRM=yes 로 재실행
"""
import os
from datetime import datetime, timezone, timedelta

import psycopg2

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://capd_user:capd_pass@db:5432/capd",
)
PATIENT_NAME = os.environ.get("PATIENT_NAME", "박차원")

KST = timezone(timedelta(hours=9))
RECORD_DATE = os.environ.get("RECORD_DATE") or datetime.now(KST).strftime("%Y-%m-%d")
CONFIRM = os.environ.get("CONFIRM", "").lower() == "yes"

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = False
cur = conn.cursor()

# 1) 대상 환자 찾기 (동명이인 방지)
cur.execute(
    "SELECT id, name FROM users WHERE name = %s AND role = 'patient'",
    (PATIENT_NAME,),
)
patients = cur.fetchall()
if len(patients) == 0:
    print(f"❌ '{PATIENT_NAME}' 이름의 환자를 찾을 수 없습니다.")
    raise SystemExit(1)
if len(patients) > 1:
    print(f"⚠️ '{PATIENT_NAME}' 동명이인 {len(patients)}명 발견: {patients}")
    print("   user id 로 직접 지정이 필요합니다. (스크립트의 patient 선택 부분 수정)")
    raise SystemExit(1)

patient_id, patient_name = patients[0]
print(f"대상 환자: {patient_name} (id={patient_id})")
print(f"대상 날짜: {RECORD_DATE}")

# 2) 해당 날짜의 daily_record 찾기
cur.execute(
    "SELECT id, status FROM daily_records WHERE patient_id = %s AND record_date = %s",
    (patient_id, RECORD_DATE),
)
records = cur.fetchall()
if not records:
    print("ℹ️ 해당 날짜에 삭제할 기록이 없습니다. 이미 비어 있는 상태입니다.")
    raise SystemExit(0)

record_ids = [r[0] for r in records]
print(f"삭제 대상 daily_record: {records}  (총 {len(record_ids)}건)")

# 3) 연결 데이터 건수 미리 집계
def count(table):
    cur.execute(
        f"SELECT COUNT(*) FROM {table} WHERE daily_record_id = ANY(%s)",
        (record_ids,),
    )
    return cur.fetchone()[0]

print(f"  ├─ survey_responses : {count('survey_responses')}건")
print(f"  ├─ ai_questions     : {count('ai_questions')}건")
print(f"  └─ exchange_records : {count('exchange_records')}건")

if not CONFIRM:
    print("\n🔎 DRY-RUN 입니다. 실제로 삭제하지 않았습니다.")
    print("   삭제하려면 CONFIRM=yes 환경변수와 함께 다시 실행하세요.")
    conn.rollback()
    raise SystemExit(0)

# 4) 자식 → 부모 순서로 삭제
cur.execute("DELETE FROM survey_responses WHERE daily_record_id = ANY(%s)", (record_ids,))
cur.execute("DELETE FROM ai_questions     WHERE daily_record_id = ANY(%s)", (record_ids,))
cur.execute("DELETE FROM exchange_records WHERE daily_record_id = ANY(%s)", (record_ids,))
cur.execute("DELETE FROM daily_records    WHERE id = ANY(%s)", (record_ids,))

conn.commit()
print(f"\n✅ {patient_name} 의 {RECORD_DATE} 기록 {len(record_ids)}건을 완전히 삭제했습니다.")

cur.close()
conn.close()
