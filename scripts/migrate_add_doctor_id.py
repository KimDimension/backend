"""
마이그레이션: users 테이블에 doctor_id 컬럼 추가

실행법:
  cd ~/capd
  python backend/scripts/migrate_add_doctor_id.py
"""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://capd_user:capd_pass@localhost:5432/capd",
)

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    # 컬럼이 이미 있으면 skip
    exists = conn.execute(text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name='users' AND column_name='doctor_id'
    """)).fetchone()

    if exists:
        print("doctor_id 컬럼이 이미 존재합니다. 스킵합니다.")
    else:
        conn.execute(text("""
            ALTER TABLE users
            ADD COLUMN doctor_id BIGINT REFERENCES users(id) ON DELETE SET NULL;
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_users_doctor_id ON users(doctor_id);
        """))
        conn.commit()
        print("doctor_id 컬럼 추가 완료.")
