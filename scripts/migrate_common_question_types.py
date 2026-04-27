"""
마이그레이션: 공통 질문 타입 확장

변경 내용:
  1. common_questions.question_type 컬럼 추가 (ai_question_type_enum 재사용, 기본값 yes_no)
  2. common_questions.options 컬럼 추가 (JSON 배열 문자열, nullable)

실행 방법 (로컬):
    $env:DATABASE_URL = "postgresql://capd_user:capd_pass@localhost:5432/capd"
    python backend/scripts/migrate_common_question_types.py

서버 실행 방법:
    cd ~/capd
    docker compose -f docker-compose.prod.yml exec backend python scripts/migrate_common_question_types.py

멱등성: 이미 적용된 경우 건너뜀.
"""

import os
import psycopg2

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://capd_user:capd_pass@localhost:5432/capd"
)


def main():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    # ── 1. ai_question_type_enum 존재 확인 (없으면 생성) ──────
    cur.execute("""
        SELECT 1 FROM pg_type WHERE typname = 'ai_question_type_enum'
    """)
    if cur.fetchone():
        print("✅ ai_question_type_enum 이미 존재 — 재사용")
    else:
        cur.execute("""
            CREATE TYPE ai_question_type_enum
            AS ENUM ('yes_no', 'single_select', 'multi_select', 'short_text');
        """)
        print("✅ ai_question_type_enum 생성 완료")

    # ── 2. common_questions.question_type 컬럼 추가 ──────────
    cur.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'common_questions' AND column_name = 'question_type'
    """)
    if cur.fetchone():
        print("✅ common_questions.question_type 이미 존재 — 건너뜀")
    else:
        cur.execute("""
            ALTER TABLE common_questions
            ADD COLUMN question_type ai_question_type_enum NOT NULL DEFAULT 'yes_no';
        """)
        print("✅ common_questions.question_type 컬럼 추가 완료 (기존 데이터 → yes_no)")

    # ── 3. common_questions.options 컬럼 추가 ────────────────
    cur.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'common_questions' AND column_name = 'options'
    """)
    if cur.fetchone():
        print("✅ common_questions.options 이미 존재 — 건너뜀")
    else:
        cur.execute("""
            ALTER TABLE common_questions
            ADD COLUMN options TEXT NULL;
        """)
        print("✅ common_questions.options 컬럼 추가 완료")

    cur.close()
    conn.close()
    print("\n✅ 마이그레이션 완료.")


if __name__ == "__main__":
    main()
