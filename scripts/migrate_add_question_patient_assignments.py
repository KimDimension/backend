"""
Migration: 공통 질문 환자별 타겟팅 기능 추가
- common_questions 에 target_all_patients BOOLEAN 컬럼 추가
- question_patient_assignments 테이블 생성
"""

import os
import sys

import psycopg2

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://capd_user:capd_pass@db:5432/capd",
)


def run():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # 1. target_all_patients 컬럼 추가 (이미 존재하면 skip)
        cur.execute(
            """
            ALTER TABLE common_questions
            ADD COLUMN IF NOT EXISTS target_all_patients BOOLEAN NOT NULL DEFAULT TRUE;
            """
        )
        print("✅ common_questions.target_all_patients 컬럼 추가 (또는 이미 존재)")

        # 2. question_patient_assignments 테이블 생성
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS question_patient_assignments (
                id              BIGSERIAL PRIMARY KEY,
                question_id     BIGINT NOT NULL
                                    REFERENCES common_questions(id) ON DELETE CASCADE,
                patient_id      BIGINT NOT NULL
                                    REFERENCES users(id) ON DELETE CASCADE,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_qpa_question_patient UNIQUE (question_id, patient_id)
            );
            """
        )
        print("✅ question_patient_assignments 테이블 생성 (또는 이미 존재)")

        # 3. 인덱스
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_qpa_question_id
                ON question_patient_assignments (question_id);
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_qpa_patient_id
                ON question_patient_assignments (patient_id);
            """
        )
        print("✅ 인덱스 생성 완료")

        conn.commit()
        print("\n🎉 마이그레이션 완료")

    except Exception as e:
        conn.rollback()
        print(f"❌ 오류 발생: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    run()
