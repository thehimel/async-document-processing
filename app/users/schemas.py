import uuid

from pydantic import BaseModel

from app.users.models import UserRole


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    image: str | None
    is_active: bool
    role: UserRole

    model_config = {"from_attributes": True}


class UserAdminUpdate(BaseModel):
    """Fields editable by an admin: role and active status only."""

    role: UserRole | None = None
    is_active: bool | None = None
