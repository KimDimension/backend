"""
migrate_add_rejected_reason.py

ai_questions 테이블에 rejected_reason 컬럼 추가.
의사가 AI 질문을 거절할 때 이유를 기록할 수 있도록 함.

실행:
    cd backend
    python -m scripts.migrate_add_rejected_reason
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.database import engine


def main():
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'ai_questions' AND column_name = 'rejected_reason'
        """))
        if result.fetchone():
            print("이미 존재합니다. 스킵.")
            return

        conn.execute(text("ALTER TABLE ai_questions ADD COLUMN rejected_reason TEXT"))
        conn.commit()
        print("ai_questions.rejected_reason 컬럼 추가 완료.")


if __name__ == "__main__":
    main()
