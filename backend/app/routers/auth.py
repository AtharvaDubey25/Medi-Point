from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from prisma import Prisma
import httpx
from jose import jwt

from app.config import settings
from app.prisma_client import get_db
from app.schemas.user import UserRegister, UserLogin, UserResponse, TokenResponse
from app.services.auth_service import hash_password, verify_password, create_access_token, validate_password_strength
from app.dependencies.rate_limiter import login_limiter, register_limiter

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister, db: Prisma = Depends(get_db), _=Depends(register_limiter)):
    pw_error = validate_password_strength(data.password)
    if pw_error:
        raise HTTPException(status_code=400, detail=f"Weak password: {pw_error}")

    existing = await db.user.find_first(where={"email": data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = await db.user.create(data={
        "email": data.email,
        "password_hash": hash_password(data.password),
        "full_name": data.full_name,
        "phone": data.phone,
        "role": "PATIENT",
    })

    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            phone=user.phone,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: Prisma = Depends(get_db), _=Depends(login_limiter)):
    user = await db.user.find_first(where={"email": data.email})
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account is disabled")

    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            phone=user.phone,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    )


@router.get("/google/callback")
async def google_callback(code: str, state: str, db: Prisma = Depends(get_db)):
    try:
        payload = jwt.decode(state, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        subject = payload.get("sub")
        if subject is None:
            raise HTTPException(status_code=401, detail="Invalid token in state")
        user_id = int(subject)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token in state")

    user = await db.user.find_first(where={"id": user_id})
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            }
        )
        if res.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Failed to retrieve Google token: {res.text}")
        
        token_data = res.json()
        access_token = token_data.get("access_token")
        
        await db.user.update(
            where={"id": user.id},
            data={"google_calendar_token": access_token}
        )

    redirect_path = "/patient/dashboard" if user.role == "PATIENT" else "/doctor/dashboard"
    return RedirectResponse(url=f"http://localhost:3000{redirect_path}?calendar=linked")
