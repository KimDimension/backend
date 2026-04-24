"""
마이그레이션: AI 질문 타입 확장 + 챗봇 테이블 제거

변경 내용:
  1. ai_question_type_enum ENUM 타입 생성 (yes_no, single_select, multi_select, short_text)
  2. ai_questions 테이블에 question_type, options 컬럼 추가
  3. conversation_messages 테이블 DROP
  4. conversations 테이블 DROP
  5. 관련 ENUM 타입 제거 (conversation_status_enum, message_role_enum)

실행 방법 (로컬):
    $env:DATABASE_URL = "postgresql://capd_user:capd_pass@localhost:5432/capd"
    python backend/scripts/migrate_ai_question_types.py

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

    # ── 1. ai_question_type_enum 생성 ─────────────────────────
    cur.execute("""
        SELECT 1 FROM pg_type WHERE typname = 'ai_question_type_enum'
    """)
    if cur.fetchone():
        print("✅ ai_question_type_enum 이미 존재 — 건너뜀")
    else:
        cur.execute("""
            CREATE TYPE ai_question_type_enum
            AS ENUM ('yes_no', 'single_select', 'multi_select', 'short_text');
        """)
        print("✅ ai_question_type_enum 생성 완료")

    # ── 2. ai_questions.question_type 컬럼 추가 ───────────────
    cur.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ai_questions' AND column_name = 'question_type'
    """)
    if cur.fetchone():
        print("✅ ai_questions.question_type 이미 존재 — 건너뜀")
    else:
        cur.execute("""
            ALTER TABLE ai_questions
            ADD COLUMN question_type ai_question_type_enum NOT NULL DEFAULT 'yes_no';
        """)
        print("✅ ai_questions.question_type 컬럼 추가 완료")

    # ── 3. ai_questions.options 컬럼 추가 ────────────────────
    cur.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ai_questions' AND column_name = 'options'
    """)
    if cur.fetchone():
        print("✅ ai_questions.options 이미 존재 — 건너뜀")
    else:
        cur.execute("""
            ALTER TABLE ai_questions
            ADD COLUMN options TEXT NULL;
        """)
        print("✅ ai_questions.options 컬럼 추가 완료")

    # ── 4. conversation_messages 테이블 DROP ──────────────────
    cur.execute("""
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'conversation_messages'
    """)
    if cur.fetchone():
        cur.execute("DROP TABLE conversation_messages CASCADE;")
        print("✅ conversation_messages 테이블 삭제 완료")
    else:
        print("✅ conversation_messages 없음 — 건너뜀")

    # ── 5. conversations 테이블 DROP ──────────────────────────
    cur.execute("""
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'conversations'
    """)
    if cur.fetchone():
        cur.execute("DROP TABLE conversations CASCADE;")
        print("✅ conversations 테이블 삭제 완료")
    else:
        print("✅ conversations 없음 — 건너뜀")

    # ── 6. 관련 ENUM 타입 제거 ────────────────────────────────
    for enum_name in ("conversation_status_enum", "message_role_enum"):
        cur.execute(f"SELECT 1 FROM pg_type WHERE typname = '{enum_name}'")
        if cur.fetchone():
            cur.execute(f"DROP TYPE IF EXISTS {enum_name};")
            print(f"✅ {enum_name} 타입 삭제 완료")
        else:
            print(f"✅ {enum_name} 없음 — 건너뜀")

    cur.close()
    conn.close()
    print("\n✅ 마이그레이션 완료.")


if __name__ == "__main__":
    main()
