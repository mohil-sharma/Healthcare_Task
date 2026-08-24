"""FastAPI dependencies, primarily for authentication and role-based access control."""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.models.enums import UserRole
from app.schemas.auth import TokenPayload

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login"
)


async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str = Depends(reusable_oauth2)
) -> User:
    """Validate the JWT token and return the current user."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )

    if token_data.sub is None:
        raise HTTPException(status_code=403, detail="Invalid token payload")

    user_id = int(token_data.sub)
    
    # We eagerly load the doctor_profile so it's ready for the response schema
    stmt = (
        select(User)
        .options(selectinload(User.doctor_profile))
        .where(User.id == user_id)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return user


def require_role(required_role: UserRole):
    """
    Dependency factory to restrict an endpoint to a specific role.
    Usage:
        def my_endpoint(user: User = Depends(require_role(UserRole.patient))):
            ...
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"The user doesn't have enough privileges. Requires: {required_role.value}",
            )
        return current_user

    return role_checker


# Convenience dependencies
get_current_patient = require_role(UserRole.patient)
get_current_doctor = require_role(UserRole.doctor)
get_current_admin = require_role(UserRole.admin)
