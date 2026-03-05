import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.backend import current_active_user, current_admin
from app.database import get_db
from app.users.dependencies import get_user_by_id
from app.users.errors import CannotDeleteSelfError
from app.users.models import User
from app.users.routes import RouteName
from app.users.schemas import UserAdminUpdate, UserRead

router = APIRouter()

admin_router = APIRouter(dependencies=[Depends(current_admin)])


@router.get("/me", response_model=UserRead, name=RouteName.users_get_me)
async def get_me(user: User = Depends(current_active_user)):
    return user


@admin_router.get("/{id}", response_model=UserRead, name=RouteName.users_get_by_id)
async def get_user(user: User = Depends(get_user_by_id)):
    return user


@admin_router.patch("/{id}", response_model=UserRead, name=RouteName.users_update_by_id)
async def update_user(
    user_update: UserAdminUpdate,
    user: User = Depends(get_user_by_id),
    session: AsyncSession = Depends(get_db),
):
    for field, value in user_update.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    await session.commit()
    await session.refresh(user)
    return user


@admin_router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT, name=RouteName.users_delete_by_id)
async def delete_user(
    id: uuid.UUID,
    requesting_user: User = Depends(current_admin),
    user: User = Depends(get_user_by_id),
    session: AsyncSession = Depends(get_db),
):
    if id == requesting_user.id:
        raise CannotDeleteSelfError()
    await session.delete(user)
    await session.commit()


# Must stay at the bottom — include_router copies routes registered on admin_router at call time.
router.include_router(admin_router)
