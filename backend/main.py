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

from pydantic import BaseModel

from sqlalchemy.orm import Session

from jose import jwt

from pwdlib import PasswordHash

from supabase import create_client

from database import SessionLocal, engine

from models import Base, User, Article


# =========================================================
# DATABASE
# =========================================================

Base.metadata.create_all(bind=engine)


# =========================================================
# APP
# =========================================================

app = FastAPI(
    title="FAKEPRESS API",
    description="FAKEPRESS Fake News API",
    version="1.0.0",
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# ENV
# =========================================================

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "change-this-secret-key",
)

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7


SUPABASE_URL = os.getenv(
    "SUPABASE_URL"
)

SUPABASE_SERVICE_ROLE_KEY = os.getenv(
    "SUPABASE_SERVICE_ROLE_KEY"
)


# =========================================================
# SUPABASE
# =========================================================

supabase = None

if (
    SUPABASE_URL
    and SUPABASE_SERVICE_ROLE_KEY
):
    supabase = create_client(
        SUPABASE_URL,
        SUPABASE_SERVICE_ROLE_KEY,
    )


# =========================================================
# PASSWORD
# =========================================================

pwd_context = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(
    password: str,
    password_hash: str,
) -> bool:
    return pwd_context.verify(
        password,
        password_hash,
    )


# =========================================================
# JWT
# =========================================================

security = HTTPBearer()


def create_access_token(
    user_id: int,
):
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
# DATABASE SESSION
# =========================================================

def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


# =========================================================
# CURRENT USER
# =========================================================

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),
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

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="로그인이 만료되었습니다.",
        )

    except jwt.JWTError:
        raise HTTPException(
            status_code=401,
            detail="유효하지 않은 토큰입니다.",
        )

    try:
        user_id = int(user_id)

    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="유효하지 않은 사용자입니다.",
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

    if user.is_banned == 1:
        raise HTTPException(
            status_code=403,
            detail="정지된 계정입니다.",
        )

    return user


# =========================================================
# ADMIN CHECK
# =========================================================

def get_admin_user(
    current_user: User = Depends(
        get_current_user
    ),
):
    if current_user.is_admin != 1:
        raise HTTPException(
            status_code=403,
            detail="관리자만 사용할 수 있습니다.",
        )

    return current_user


# =========================================================
# SCHEMAS
# =========================================================

class RegisterRequest(BaseModel):
    nickname: str
    password: str


class LoginRequest(BaseModel):
    nickname: str
    password: str


class ArticleRequest(BaseModel):
    title: str
    subtitle: str = ""
    author: str = ""
    date: str = ""
    content: str = ""
    image: str | None = None


# =========================================================
# BASIC
# =========================================================

@app.get("/")
def root():
    return {
        "message": "FAKEPRESS API is running"
    }


# =========================================================
# REGISTER
# =========================================================

@app.post("/auth/register")
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    nickname = request.nickname.strip()
    password = request.password

    if not nickname:
        raise HTTPException(
            status_code=400,
            detail="닉네임을 입력해주세요.",
        )

    if len(nickname) > 20:
        raise HTTPException(
            status_code=400,
            detail="닉네임은 20자 이하로 입력해주세요.",
        )

    if not password:
        raise HTTPException(
            status_code=400,
            detail="비밀번호를 입력해주세요.",
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
        password_hash=hash_password(password),
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
            "is_admin": user.is_admin,
            "is_banned": user.is_banned,
        },
    }


# =========================================================
# LOGIN
# =========================================================

@app.post("/auth/login")
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    nickname = request.nickname.strip()

    user = (
        db.query(User)
        .filter(User.nickname == nickname)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="닉네임 또는 비밀번호가 올바르지 않습니다.",
        )

    if not verify_password(
        request.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=401,
            detail="닉네임 또는 비밀번호가 올바르지 않습니다.",
        )

    if user.is_banned == 1:
        raise HTTPException(
            status_code=403,
            detail="정지된 계정입니다.",
        )

    token = create_access_token(
        user.id
    )

    return {
        "message": "로그인되었습니다.",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "nickname": user.nickname,
            "is_admin": user.is_admin,
            "is_banned": user.is_banned,
        },
    }


# =========================================================
# ME
# =========================================================

@app.get("/auth/me")
def me(
    current_user: User = Depends(
        get_current_user
    ),
):
    return {
        "id": current_user.id,
        "nickname": current_user.nickname,
        "is_admin": current_user.is_admin,
        "is_banned": current_user.is_banned,
        "created_at": current_user.created_at,
    }


# =========================================================
# IMAGE UPLOAD
# =========================================================

@app.post("/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(
        get_current_user
    ),
):
    if supabase is None:
        raise HTTPException(
            status_code=500,
            detail="Supabase Storage가 설정되지 않았습니다.",
        )

    if not file.content_type:
        raise HTTPException(
            status_code=400,
            detail="파일 형식을 확인할 수 없습니다.",
        )

    if not file.content_type.startswith(
        "image/"
    ):
        raise HTTPException(
            status_code=400,
            detail="이미지 파일만 업로드할 수 있습니다.",
        )

    contents = await file.read()

    if not contents:
        raise HTTPException(
            status_code=400,
            detail="빈 파일입니다.",
        )

    extension = Path(
        file.filename or ""
    ).suffix.lower()

    if not extension:
        extension = ".jpg"

    filename = (
        f"{uuid.uuid4().hex}"
        f"{extension}"
    )

    bucket_name = "images"

    try:
        supabase.storage.from_(
            bucket_name
        ).upload(
            filename,
            contents,
            {
                "content-type": file.content_type,
                "upsert": "false",
            },
        )

        public_url = (
            supabase.storage
            .from_(bucket_name)
            .get_public_url(filename)
        )

        return {
            "message": "이미지가 업로드되었습니다.",
            "image": public_url,
            "image_url": public_url,
        }

    except Exception as error:
        print(
            "IMAGE UPLOAD ERROR:",
            error,
        )

        raise HTTPException(
            status_code=500,
            detail="이미지 업로드에 실패했습니다.",
        )


# =========================================================
# GET ARTICLES
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
# GET ONE ARTICLE
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
# CREATE ARTICLE
# 3분 도배 방지
# =========================================================

@app.post("/articles")
def create_article(
    request: ArticleRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)

    # -----------------------------------------------------
    # 3분 쿨타임 확인
    # -----------------------------------------------------

    if current_user.last_article_created_at:

        last_time = (
            current_user.last_article_created_at
        )

        if last_time.tzinfo is None:
            last_time = last_time.replace(
                tzinfo=timezone.utc
            )

        elapsed = now - last_time

        cooldown = timedelta(
            minutes=3
        )

        if elapsed < cooldown:

            remaining = (
                cooldown - elapsed
            )

            remaining_seconds = int(
                remaining.total_seconds()
            )

            minutes = (
                remaining_seconds // 60
            )

            seconds = (
                remaining_seconds % 60
            )

            if minutes > 0:
                message = (
                    "도배 방지를 위해 "
                    f"{minutes}분 "
                    f"{seconds}초 후에 "
                    "다시 기사를 작성할 수 있습니다."
                )

            else:
                message = (
                    "도배 방지를 위해 "
                    f"{seconds}초 후에 "
                    "다시 기사를 작성할 수 있습니다."
                )

            raise HTTPException(
                status_code=429,
                detail=message,
            )

    # -----------------------------------------------------
    # 기사 생성
    # -----------------------------------------------------

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

    # 마지막 기사 작성 시간 기록
    current_user.last_article_created_at = now

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
# UPDATE ARTICLE
# 본인 기사 또는 관리자만 수정 가능
# =========================================================

@app.put("/articles/{article_id}")
def update_article(
    article_id: int,
    request: ArticleRequest,
    current_user: User = Depends(
        get_current_user
    ),
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

    # 본인 기사 또는 관리자만 수정
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

    if request.image is not None:
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
# DELETE ARTICLE
# 본인 기사 또는 관리자만 삭제 가능
# =========================================================

@app.delete("/articles/{article_id}")
def delete_article(
    article_id: int,
    current_user: User = Depends(
        get_current_user
    ),
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

    # 본인 기사 또는 관리자만 삭제
    if (
        article.owner_id != current_user.id
        and current_user.is_admin != 1
    ):
        raise HTTPException(
            status_code=403,
            detail="삭제 권한이 없습니다.",
        )

    db.delete(article)
    db.commit()

    return {
        "message": "기사가 삭제되었습니다."
    }


# =========================================================
# ADMIN - USERS
# =========================================================

@app.get("/admin/users")
def admin_users(
    admin: User = Depends(
        get_admin_user
    ),
    db: Session = Depends(get_db),
):
    users = (
        db.query(User)
        .order_by(
            User.id.asc()
        )
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
# ADMIN - MAKE ADMIN
# =========================================================

@app.post("/admin/make-admin/{user_id}")
def make_admin(
    user_id: int,
    admin: User = Depends(
        get_admin_user
    ),
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
# ADMIN - REMOVE ADMIN
# =========================================================

@app.post("/admin/remove-admin/{user_id}")
def remove_admin(
    user_id: int,
    admin: User = Depends(
        get_admin_user
    ),
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

    # 자기 자신은 관리자 해제 방지
    if user.id == admin.id:
        raise HTTPException(
            status_code=400,
            detail="자기 자신의 관리자 권한은 해제할 수 없습니다.",
        )

    user.is_admin = 0

    db.commit()
    db.refresh(user)

    return {
        "message": "관리자 권한이 해제되었습니다.",
        "user": {
            "id": user.id,
            "nickname": user.nickname,
            "is_admin": user.is_admin,
        },
    }


# =========================================================
# ADMIN - BAN
# =========================================================

@app.post("/admin/ban/{user_id}")
def ban_user(
    user_id: int,
    admin: User = Depends(
        get_admin_user
    ),
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

    if user.id == admin.id:
        raise HTTPException(
            status_code=400,
            detail="자기 자신을 정지할 수 없습니다.",
        )

    user.is_banned = 1

    db.commit()
    db.refresh(user)

    return {
        "message": "사용자가 정지되었습니다.",
        "user": {
            "id": user.id,
            "nickname": user.nickname,
            "is_banned": user.is_banned,
        },
    }


# =========================================================
# ADMIN - UNBAN
# =========================================================

@app.post("/admin/unban/{user_id}")
def unban_user(
    user_id: int,
    admin: User = Depends(
        get_admin_user
    ),
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
    db.refresh(user)

    return {
        "message": "사용자 정지가 해제되었습니다.",
        "user": {
            "id": user.id,
            "nickname": user.nickname,
            "is_banned": user.is_banned,
        },
    }


# =========================================================
# ADMIN - GET ALL ARTICLES
# =========================================================

@app.get("/admin/articles")
def admin_articles(
    admin: User = Depends(
        get_admin_user
    ),
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
# ADMIN - DELETE ARTICLE
# =========================================================

@app.delete("/admin/articles/{article_id}")
def admin_delete_article(
    article_id: int,
    admin: User = Depends(
        get_admin_user
    ),
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
        "message": "기사가 삭제되었습니다."
    }