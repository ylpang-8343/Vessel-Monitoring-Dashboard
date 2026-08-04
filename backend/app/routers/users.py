"""Admin-only user/role management, backing the Settings → Users tab. Every route on this
router requires the ADMIN role (enforced once, at the router level, rather than per-route)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import require_admin
from app.models import User, UserRole
from app.schemas import RoleUpdateRequest, UserOut

router = APIRouter(prefix="/api/users", tags=["users"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    """List every account, for the Users tab's table (and its client-side email search)."""
    return db.query(User).order_by(User.email).all()


@router.patch("/{user_id}/role", response_model=UserOut)
def update_user_role(user_id: int, payload: RoleUpdateRequest, db: Session = Depends(get_db)):
    """Promote or demote a user. Demoting the *last* remaining admin is blocked with a 409 -
    without this guard, an admin could demote themselves (or the only other admin) and leave
    nobody able to manage roles at all, including no way back in short of another
    `promote-admin` CLI run."""
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
