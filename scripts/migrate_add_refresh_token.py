"""
migrate_add_refresh_token.py

users 테이블에 refresh_token 컬럼 추가.
기존 세션은 모두 NULL로 초기화되므로, 배포 후 유저들이 재로그인 필요.

실행:
    cd backend
    python -m scripts.migrate_add_refresh_token
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.database import engine


def main():
    with engine.connect() as conn:
        # 컬럼이 이미 있으면 스킵
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'refresh_token'
        """))
        if result.fetchone():
            print("✅ refresh_token 컬럼이 이미 존재합니다. 스킵.")
            return

        conn.execute(text("ALTER TABLE users ADD COLUMN refresh_token TEXT"))
        conn.commit()
        print("✅ users.refresh_token 컬럼 추가 완료.")
        print("⚠️  기존 사용자는 재로그인이 필요합니다.")


if __name__ == "__main__":
    main()
