"""
migrate_add_gender_address.py
─────────────────────────────
users 테이블에 gender / address 컬럼 추가.
기존 환자: gender='m' (남), address='서울' 일괄 설정.

실행:
  docker compose -f docker-compose.prod.yml exec backend \
    python scripts/migrate_add_gender_address.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from app.core.database import DATABASE_URL

def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur  = conn.cursor()

    # 1. 컬럼 추가 (이미 있으면 무시)
    print("▶ users.gender 컬럼 추가 중...")
    cur.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS gender  VARCHAR(1)   DEFAULT NULL,
        ADD COLUMN IF NOT EXISTS address VARCHAR(200) DEFAULT NULL;
    """)
    conn.commit()
    print("  ✓ 컬럼 추가 완료")

    # 2. 기존 환자 일괄 업데이트
    print("▶ 기존 환자 gender='m', address='서울' 설정 중...")
    cur.execute("""
        UPDATE users
        SET gender  = 'm',
            address = '서울'
        WHERE role = 'patient'
          AND gender IS NULL;
    """)
    updated = cur.rowcount
    conn.commit()
    print(f"  ✓ {updated}명 업데이트 완료")

    cur.close()
    conn.close()
    print("✅ 마이그레이션 완료!")

if __name__ == "__main__":
    main()
