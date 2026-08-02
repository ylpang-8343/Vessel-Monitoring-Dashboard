from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import require_admin
from app.models import User, UserRole
from app.schemas import RoleUpdateRequest, UserOut

router = APIRouter(prefix="/api/users", tags=["users"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).order_by(User.email).all()


@router.patch("/{user_id}/role", response_model=UserOut)
def update_user_role(user_id: int, payload: RoleUpdateRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if user.role == UserRole.ADMIN and payload.role == UserRole.USER:
        admin_count = db.query(User).filter(User.role == UserRole.ADMIN).count()
        if admin_count <= 1:
            raise HTTPException(status_code=409, detail="Cannot demote the last remaining admin")

    user.role = payload.role
    db.commit()
    db.refresh(user)
    return user
