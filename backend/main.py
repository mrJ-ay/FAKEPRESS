import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    UploadFile,
    File,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from sqlalchemy.orm import Session
from jose import jwt, JWTError
from pwdlib import PasswordHash
from supabase import create_client, Client

from database import Base, engine, get_db
from models import User, Article
from schemas import (
    RegisterRequest,
    LoginRequest,
    ArticleRequest,
)


# =========================================================
# 기본 설정
# =========================================================

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "dev-only-change-me",
)

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7


# =========================================================
# Supabase
# =========================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv(
    "SUPABASE_SERVICE_ROLE_KEY"
)

if not SUPABASE_URL:
    raise RuntimeError(
        "SUPABASE_URL 환경변수가 설정되지 않았습니다."
    )

if not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError(
        "SUPABASE_SERVICE_ROLE_KEY 환경변수가 설정되지 않았습니다."
    )

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY,
)

STORAGE_BUCKET = "article-images"


# =========================================================
# FastAPI
# =========================================================

app = FastAPI(
    title="FAKEPRESS API",
    version="1.0.0",
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://fakepress-1.onrender.com",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# Database
# =========================================================

Base.metadata.create_all(
    bind=engine
)


# =========================================================
# Password
# =========================================================

password_hash = PasswordHash.recommended()


# =========================================================
# JWT
# =========================================================

security = HTTPBearer()


def create_access_token(user_id: int):
    expire = (
        datetime.now(timezone.utc)
        + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    )

    payload = {
        "sub": str(user_id),
        "exp": expire,
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


# =========================================================
# Current User
# =========================================================

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="유효하지 않은 토큰입니다.",
            )

        user_id = int(user_id)

    except (JWTError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="유효하지 않은 토큰입니다.",
        )

    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="사용자를 찾을 수 없습니다.",
        )

    if user.is_banned:
        raise HTTPException(
            status_code=403,
            detail="차단된 계정입니다.",
        )

    return user


# =========================================================
# Admin
# =========================================================

def get_admin_user(
    current_user: User = Depends(get_current_user),
):
    if current_user.is_admin != 1:
        raise HTTPException(
            status_code=403,
            detail="관리자만 사용할 수 있습니다.",
        )

    return current_user


# =========================================================
# Root
# =========================================================

@app.get("/")
def root():
    return {
        "message": "FAKEPRESS API is running"
    }


# =========================================================
# Register
# =========================================================

@app.post("/auth/register")
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    nickname = request.nickname.strip()

    if len(nickname) < 2:
        raise HTTPException(
            status_code=400,
            detail="닉네임은 2자 이상이어야 합니다.",
        )

    if len(request.password) < 4:
        raise HTTPException(
            status_code=400,
            detail="비밀번호는 4자 이상이어야 합니다.",
        )

    existing = (
        db.query(User)
        .filter(User.nickname == nickname)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="이미 존재하는 닉네임입니다.",
        )

    user = User(
        nickname=nickname,
        password_hash=password_hash.hash(
            request.password
        ),
        is_admin=0,
        is_banned=0,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "message": "회원가입이 완료되었습니다.",
        "user": {
            "id": user.id,
            "nickname": user.nickname,
        },
    }


# =========================================================
# Login
# =========================================================

@app.post("/auth/login")
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.nickname == request.nickname)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="닉네임 또는 비밀번호가 올바르지 않습니다.",
        )

    if user.is_banned:
        raise HTTPException(
            status_code=403,
            detail="차단된 계정입니다.",
        )

    try:
        valid = password_hash.verify(
            request.password,
            user.password_hash,
        )
    except Exception:
        valid = False

    if not valid:
        raise HTTPException(
            status_code=401,
            detail="닉네임 또는 비밀번호가 올바르지 않습니다.",
        )

    token = create_access_token(user.id)

    return {
        "message": "로그인되었습니다.",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "nickname": user.nickname,
            "is_admin": user.is_admin,
        },
    }


# =========================================================
# Me
# =========================================================

@app.get("/auth/me")
def me(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": current_user.id,
        "nickname": current_user.nickname,
        "is_admin": current_user.is_admin,
        "is_banned": current_user.is_banned,
    }


# =========================================================
# Image Upload - Supabase Storage
# =========================================================

@app.post("/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if not file.content_type:
        raise HTTPException(
            status_code=400,
            detail="파일 형식을 확인할 수 없습니다.",
        )

    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="이미지 파일만 업로드할 수 있습니다.",
        )

    extension = Path(
        file.filename or ""
    ).suffix.lower()

    if not extension:
        extension = ".jpg"

    # 파일명 충돌 방지
    filename = (
        f"{uuid.uuid4().hex}"
        f"{extension}"
    )

    # 사용자별 폴더
    storage_path = (
        f"{current_user.id}/{filename}"
    )

    try:
        contents = await file.read()

        supabase.storage.from_(
            STORAGE_BUCKET
        ).upload(
            storage_path,
            contents,
            {
                "content-type": file.content_type,
                "upsert": False,
            },
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"이미지 업로드 실패: {str(e)}",
        )

    # Public URL 생성
    try:
        public_url = (
            supabase.storage
            .from_(STORAGE_BUCKET)
            .get_public_url(storage_path)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"이미지 URL 생성 실패: {str(e)}",
        )

    return {
        "message": "이미지 업로드 성공",
        "url": public_url,
        "path": storage_path,
    }


# =========================================================
# Articles - Create
# =========================================================

@app.post("/articles")
def create_article(
    request: ArticleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    article = Article(
        title=request.title,
        subtitle=request.subtitle,
        author=request.author,
        date=request.date,
        content=request.content,
        image=request.image,
        owner_id=current_user.id,
    )

    db.add(article)
    db.commit()
    db.refresh(article)

    return {
        "message": "기사가 저장되었습니다.",
        "article": {
            "id": article.id,
            "title": article.title,
            "subtitle": article.subtitle,
            "author": article.author,
            "date": article.date,
            "content": article.content,
            "image": article.image,
            "owner_id": article.owner_id,
            "created_at": article.created_at,
            "updated_at": article.updated_at,
        },
    }


# =========================================================
# Articles - List
# =========================================================

@app.get("/articles")
def get_articles(
    db: Session = Depends(get_db),
):
    articles = (
        db.query(Article)
        .order_by(
            Article.created_at.desc()
        )
        .all()
    )

    return [
        {
            "id": article.id,
            "title": article.title,
            "subtitle": article.subtitle,
            "author": article.author,
            "date": article.date,
            "content": article.content,
            "image": article.image,
            "owner_id": article.owner_id,
            "created_at": article.created_at,
            "updated_at": article.updated_at,
        }
        for article in articles
    ]


# =========================================================
# Articles - One
# =========================================================

@app.get("/articles/{article_id}")
def get_article(
    article_id: int,
    db: Session = Depends(get_db),
):
    article = (
        db.query(Article)
        .filter(Article.id == article_id)
        .first()
    )

    if not article:
        raise HTTPException(
            status_code=404,
            detail="기사를 찾을 수 없습니다.",
        )

    return {
        "id": article.id,
        "title": article.title,
        "subtitle": article.subtitle,
        "author": article.author,
        "date": article.date,
        "content": article.content,
        "image": article.image,
        "owner_id": article.owner_id,
        "created_at": article.created_at,
        "updated_at": article.updated_at,
    }


# =========================================================
# Articles - Update
# =========================================================

@app.put("/articles/{article_id}")
def update_article(
    article_id: int,
    request: ArticleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    article = (
        db.query(Article)
        .filter(Article.id == article_id)
        .first()
    )

    if not article:
        raise HTTPException(
            status_code=404,
            detail="기사를 찾을 수 없습니다.",
        )

    if (
        article.owner_id != current_user.id
        and current_user.is_admin != 1
    ):
        raise HTTPException(
            status_code=403,
            detail="수정 권한이 없습니다.",
        )

    article.title = request.title
    article.subtitle = request.subtitle
    article.author = request.author
    article.date = request.date
    article.content = request.content
    article.image = request.image

    db.commit()
    db.refresh(article)

    return {
        "message": "기사가 수정되었습니다.",
        "article": {
            "id": article.id,
            "title": article.title,
            "subtitle": article.subtitle,
            "author": article.author,
            "date": article.date,
            "content": article.content,
            "image": article.image,
            "owner_id": article.owner_id,
            "created_at": article.created_at,
            "updated_at": article.updated_at,
        },
    }


# =========================================================
# Articles - Delete
# =========================================================

@app.delete("/articles/{article_id}")
def delete_article(
    article_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    article = (
        db.query(Article)
        .filter(Article.id == article_id)
        .first()
    )

    if not article:
        raise HTTPException(
            status_code=404,
            detail="기사를 찾을 수 없습니다.",
        )

    if (
        article.owner_id != current_user.id
        and current_user.is_admin != 1
    ):
        raise HTTPException(
            status_code=403,
            detail="삭제 권한이 없습니다.",
        )

    # 현재는 Storage의 이미지 파일은 유지
    db.delete(article)
    db.commit()

    return {
        "message": "기사가 삭제되었습니다."
    }


# =========================================================
# Admin - Users
# =========================================================

@app.get("/admin/users")
def admin_users(
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    users = (
        db.query(User)
        .order_by(User.id.asc())
        .all()
    )

    return [
        {
            "id": user.id,
            "nickname": user.nickname,
            "is_admin": user.is_admin,
            "is_banned": user.is_banned,
            "created_at": user.created_at,
        }
        for user in users
    ]


# =========================================================
# Admin - Make Admin
# =========================================================

@app.post("/admin/make-admin/{user_id}")
def make_admin(
    user_id: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="사용자를 찾을 수 없습니다.",
        )

    user.is_admin = 1

    db.commit()
    db.refresh(user)

    return {
        "message": "관리자로 지정되었습니다.",
        "user": {
            "id": user.id,
            "nickname": user.nickname,
            "is_admin": user.is_admin,
        },
    }


# =========================================================
# Admin - Remove Admin
# =========================================================

@app.post("/admin/remove-admin/{user_id}")
def remove_admin(
    user_id: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="사용자를 찾을 수 없습니다.",
        )

    user.is_admin = 0

    db.commit()
    db.refresh(user)

    return {
        "message": "관리자 권한이 제거되었습니다.",
        "user": {
            "id": user.id,
            "nickname": user.nickname,
            "is_admin": user.is_admin,
        },
    }


# =========================================================
# Admin - Ban
# =========================================================

@app.post("/admin/ban/{user_id}")
def ban_user(
    user_id: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="사용자를 찾을 수 없습니다.",
        )

    user.is_banned = 1

    db.commit()

    return {
        "message": "사용자가 차단되었습니다."
    }


# =========================================================
# Admin - Unban
# =========================================================

@app.post("/admin/unban/{user_id}")
def unban_user(
    user_id: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="사용자를 찾을 수 없습니다.",
        )

    user.is_banned = 0

    db.commit()

    return {
        "message": "사용자 차단이 해제되었습니다."
    }


# =========================================================
# Admin - Articles
# =========================================================

@app.get("/admin/articles")
def admin_articles(
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    articles = (
        db.query(Article)
        .order_by(
            Article.created_at.desc()
        )
        .all()
    )

    return [
        {
            "id": article.id,
            "title": article.title,
            "subtitle": article.subtitle,
            "author": article.author,
            "date": article.date,
            "content": article.content,
            "image": article.image,
            "owner_id": article.owner_id,
            "created_at": article.created_at,
            "updated_at": article.updated_at,
        }
        for article in articles
    ]


# =========================================================
# Admin - Delete Article
# =========================================================

@app.delete("/admin/articles/{article_id}")
def admin_delete_article(
    article_id: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    article = (
        db.query(Article)
        .filter(Article.id == article_id)
        .first()
    )

    if not article:
        raise HTTPException(
            status_code=404,
            detail="기사를 찾을 수 없습니다.",
        )

    db.delete(article)
    db.commit()

    return {
        "message": "관리자 권한으로 기사가 삭제되었습니다."
    }