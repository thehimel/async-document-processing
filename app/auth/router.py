import uuid as uuid_module
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.backend import (
    COOKIE_NAME,
    create_access_token,
    get_current_user,
    oauth,
)
from app.auth.routes import RouteName
from app.config import settings
from app.database import get_db
from app.users.models import Account, User, UserRole
from app.users.schemas import UserRead

router = APIRouter()

# Frontend destination used when no redirect_url is provided or session is lost.
_DEFAULT_REDIRECT = "/"


def _callback_uri(request: Request, redirect_url: str) -> str:
    """Build OAuth callback URI. Uses frontend origin when API is proxied (Next.js rewrites)."""
    parsed = urlparse(redirect_url)
    if parsed.scheme and parsed.netloc:
        base = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        return f"{base}/api/auth/google/callback"
    if settings.frontend_url:
        base = settings.frontend_url.rstrip("/")
        return f"{base}/api/auth/google/callback"
    return str(request.url_for(RouteName.auth_google_callback))


@router.get("/google", name=RouteName.auth_google)
async def google_login(
    request: Request,
    redirect_url: str = Query(default=_DEFAULT_REDIRECT),
):
    """Redirect the browser to the Google OAuth consent screen."""
    request.session["redirect_url"] = redirect_url
    callback_uri = _callback_uri(request, redirect_url)
    return await oauth.google.authorize_redirect(request, callback_uri)  # type: ignore[union-attr]


@router.get("/google/callback", name=RouteName.auth_google_callback)
async def google_callback(
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """
    Handle the Google OAuth callback.

    - Exchanges the authorization code for tokens.
    - Upserts User and Account rows.
    - Issues a JWT in an httpOnly cookie.
    - Redirects to the original redirect_url (stored in session).
    """
    redirect_url: str = request.session.pop("redirect_url", _DEFAULT_REDIRECT)

    token = await oauth.google.authorize_access_token(request)  # type: ignore[union-attr]
    userinfo = token["userinfo"]

    google_sub: str = userinfo["sub"]
    email: str = userinfo["email"]
    name: str = userinfo.get("name") or email.split("@")[0]
    image: str | None = userinfo.get("picture")

    # --- Upsert User + Account ---

    # 1. Account already linked to a user?
    account_result = await session.execute(
        select(Account).where(
            Account.provider_id == "google",
            Account.provider_account_id == google_sub,
        )
    )
    account: Account | None = account_result.scalar_one_or_none()

    if account:
        user: User | None = await session.get(User, account.user_id)
        if user is None or not user.is_active:
            return RedirectResponse(url=f"{redirect_url}?error=account_disabled")
        # Refresh profile fields from Google
        user.name = name
        user.image = image
    else:
        # 2. User with this email already exists (no account linked yet)?
        user_result = await session.execute(select(User).where(User.email == email))
        user = user_result.scalar_one_or_none()

        if user is None:
            user = User(
                id=uuid_module.uuid4(),
                email=email,
                name=name,
                image=image,
                role=UserRole.user,
                is_active=True,
            )
            session.add(user)
            await session.flush()  # populate user.id before referencing it in Account
        elif not user.is_active:
            return RedirectResponse(url=f"{redirect_url}?error=account_disabled")

        account = Account(
            id=uuid_module.uuid4(),
            user_id=user.id,  # type: ignore[arg-type]
            provider_id="google",
            provider_account_id=google_sub,
        )
        session.add(account)

    await session.commit()

    # --- Issue JWT cookie ---
    access_token = create_access_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,  # type: ignore[union-attr]
        }
    )

    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
    is_secure = request.url.scheme == "https"
    cookie_kwargs: dict = {
        "key": COOKIE_NAME,
        "value": access_token,
        "httponly": True,
        "secure": is_secure,
        "samesite": "none" if is_secure else "lax",
        "path": "/",
        "max_age": settings.jwt_access_token_expire_minutes * 60,
    }
    # Set cookie for the frontend domain so the proxy receives it when frontend and API are on different domains.
    parsed_redirect = urlparse(redirect_url)
    api_host = urlparse(str(request.url)).hostname
    if parsed_redirect.hostname and parsed_redirect.hostname != api_host:
        cookie_kwargs["domain"] = parsed_redirect.hostname
    response.set_cookie(**cookie_kwargs)
    return response


@router.get("/me", response_model=UserRead, name=RouteName.auth_me)
async def get_me(user: User = Depends(get_current_user)):
    """Return the currently authenticated user."""
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, name=RouteName.auth_logout)
async def logout(request: Request, response: Response):
    """Clear the session cookie."""
    is_secure = request.url.scheme == "https"
    delete_kwargs: dict = {
        "key": COOKIE_NAME,
        "path": "/",
        "httponly": True,
        "samesite": "none" if is_secure else "lax",
        "secure": is_secure,
    }
    # If the cookie was set for a different domain (frontend), we must delete with that domain.
    origin = request.headers.get("origin") or request.headers.get("referer")
    if origin:
        origin_host = urlparse(origin).hostname
        api_host = urlparse(str(request.url)).hostname
        if origin_host and origin_host != api_host:
            delete_kwargs["domain"] = origin_host
    response.delete_cookie(**delete_kwargs)
