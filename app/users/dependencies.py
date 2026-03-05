import uuid

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.users.errors import UserNotFoundError
from app.users.models import User


async def get_user_by_id(id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> User:
    """Fetch a user by UUID; raise 404 if not found."""
    user: User | None = await session.get(User, id)
    if user is None:
        raise UserNotFoundError()
    return user
