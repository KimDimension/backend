from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import (
    verify_password,
    hash_password,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_current_user,
)
from app.core.database import get_db
from app.crud.user import get_user_by_phone
from app.models.hospital import DoctorProfile, Hospital
from app.models.user import User, UserRole
from app.schemas.user import (
    LoginRequest, TokenResponse, UserResponse,
    UpdateMeRequest, DoctorProfileResponse, PatientProfileResponse,
)
from pydantic import BaseModel

class RefreshRequest(BaseModel):
    refresh_token: str

router = APIRouter(prefix="/auth", tags=["인증"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """전화번호 + 비밀번호로 로그인 → JWT 반환"""
    user = get_user_by_phone(db, phone_number=payload.phone_number)

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="전화번호 또는 비밀번호가 올바르지 않습니다.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다.",
        )

    token_data = {"sub": str(user.id), "role": user.role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        name=user.name,
        role=user.role,
    )


@router.post("/refresh")
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    """refresh_token → 새 access_token 발급"""
    from app.crud.user import get_user_by_id
    token_payload = decode_refresh_token(payload.refresh_token)
    user_id = token_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="유효하지 않은 리프레시 토큰입니다.")
    user = get_user_by_id(db, user_id=int(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다.")
    new_access_token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"access_token": new_access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """현재 로그인한 유저 기본 정보 반환"""
    return current_user


@router.get("/me/profile")
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """역할별 상세 프로필 반환 (마이페이지용)"""
    if current_user.role == UserRole.doctor:
        profile = db.query(DoctorProfile).filter_by(user_id=current_user.id).first()
        hospital = db.query(Hospital).filter_by(id=profile.hospital_id).first() if profile else None
        return DoctorProfileResponse(
            id=current_user.id,
            name=current_user.name,
            phone_number=current_user.phone_number,
            birth_date=current_user.birth_date,
            license_number=profile.license_number if profile else None,
            hospital_name=hospital.name if hospital else None,
            role=current_user.role,
        )
    else:
        hospital = db.query(Hospital).filter_by(id=current_user.hospital_id).first() if current_user.hospital_id else None
        doctor = db.query(User).filter_by(id=current_user.doctor_id).first() if current_user.doctor_id else None
        return PatientProfileResponse(
            id=current_user.id,
            name=current_user.name,
            phone_number=current_user.phone_number,
            birth_date=current_user.birth_date,
            hospital_name=hospital.name if hospital else None,
            doctor_name=doctor.name if doctor else None,
            doctor_id=current_user.doctor_id,
            self_memo=current_user.self_memo,
            gender=current_user.gender,
            address=current_user.address,
            role=current_user.role,
        )


@router.patch("/me")
def update_me(
    payload: UpdateMeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """마이페이지 수정 — 이름/생년월일/전화번호/비밀번호/환자 자기메모

    이름·생년월일·전화번호·비밀번호 변경 시 current_password 필수.
    self_memo(환자 전용)는 비밀번호 확인 없이 저장 가능.
    """
    # 비밀번호 확인이 필요한 변경 감지
    needs_pw = (
        (payload.name is not None and payload.name != current_user.name)
        or (payload.birth_date is not None and payload.birth_date != current_user.birth_date)
        or (payload.phone_number is not None and payload.phone_number != current_user.phone_number)
        or bool(payload.new_password)
    )
    if needs_pw:
        if not payload.current_password:
            raise HTTPException(status_code=400, detail="현재 비밀번호를 입력해주세요.")
        if not verify_password(payload.current_password, current_user.password_hash):
            raise HTTPException(status_code=400, detail="현재 비밀번호가 올바르지 않습니다.")

    # 이름 변경
    if payload.name is not None and payload.name != current_user.name:
        if not payload.name.strip():
            raise HTTPException(status_code=400, detail="이름을 입력해주세요.")
        current_user.name = payload.name.strip()

    # 생년월일 변경
    if payload.birth_date is not None and payload.birth_date != current_user.birth_date:
        current_user.birth_date = payload.birth_date or None

    # 전화번호 변경
    if payload.phone_number and payload.phone_number != current_user.phone_number:
        existing = get_user_by_phone(db, payload.phone_number)
        if existing:
            raise HTTPException(status_code=409, detail="이미 사용 중인 전화번호입니다.")
        current_user.phone_number = payload.phone_number

    # 비밀번호 변경
    if payload.new_password:
        if len(payload.new_password) < 6:
            raise HTTPException(status_code=400, detail="비밀번호는 6자 이상이어야 합니다.")
        current_user.password_hash = hash_password(payload.new_password)

    # 환자 자기 메모 (비밀번호 확인 불필요)
    if payload.self_memo is not None:
        if current_user.role != UserRole.patient:
            raise HTTPException(status_code=403, detail="환자만 자기 메모를 작성할 수 있습니다.")
        current_user.self_memo = payload.self_memo

    # 환자 거주지 (비밀번호 확인 불필요)
    if payload.address is not None:
        if current_user.role != UserRole.patient:
            raise HTTPException(status_code=403, detail="환자만 거주지를 수정할 수 있습니다.")
        current_user.address = payload.address or None

    db.commit()
    return {"message": "프로필이 업데이트되었습니다.", "name": current_user.name}
