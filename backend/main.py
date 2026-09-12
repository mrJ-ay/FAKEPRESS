
import os
import uuid

from datetime import datetime, timedelta, timezone

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    UploadFile,
    File
)

from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles

from sqlalchemy.orm import Session

from pydantic import BaseModel

from jose import jwt, JWTError

from database import Base, engine, get_db
from models import User, Article
from auth import hash_password, verify_password


SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "dev-only-change-me"
)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

security = HTTPBearer()

app = FastAPI(title="FAKEPRESS API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


app.mount(
    "/uploads",
    StaticFiles(directory=UPLOAD_DIR),
    name="uploads"
)


Base.metadata.create_all(bind=engine)


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
    image: str = ""


def create_access_token(user_id: int):
    expire = (
        datetime.now(timezone.utc)
        + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    payload = {
        "sub": str(user_id),
        "exp": expire
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="유효하지 않은 토큰입니다."
            )

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="유효하지 않거나 만료된 로그인입니다."
        )

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="유효하지 않은 사용자 정보입니다."
        )

    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="사용자를 찾을 수 없습니다."
        )

    if user.is_banned:
        raise HTTPException(
            status_code=403,
            detail="정지된 계정입니다."
        )

    return user


def get_admin_user(
    current_user: User = Depends(get_current_user)
):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="관리자만 사용할 수 있습니다."
        )

    return current_user


@app.get("/")
def root():
    return {"message": "FAKEPRESS API is running"}


@app.post("/register")
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db)
):
    nickname = data.nickname.strip()

    if not nickname:
        raise HTTPException(
            status_code=400,
            detail="닉네임을 입력하세요."
        )

    if len(nickname) < 2:
        raise HTTPException(
            status_code=400,
            detail="닉네임은 2글자 이상이어야 합니다."
        )

    if len(nickname) > 20:
        raise HTTPException(
            status_code=400,
            detail="닉네임은 20글자 이하이어야 합니다."
        )

    if len(data.password) < 4:
        raise HTTPException(
            status_code=400,
            detail="비밀번호는 4자리 이상이어야 합니다."
        )

    existing_user = (
        db.query(User)
        .filter(User.nickname == nickname)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="이미 존재하는 닉네임입니다."
        )

    user = User(
        nickname=nickname,
        password_hash=hash_password(data.password)
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "message": "회원가입이 완료되었습니다.",
        "user": {
            "id": user.id,
            "nickname": user.nickname
        }
    }


@app.post("/login")
def login(
    data: LoginRequest,
    db: Session = Depends(get_db)
):
    nickname = data.nickname.strip()

    user = (
        db.query(User)
        .filter(User.nickname == nickname)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="닉네임 또는 비밀번호가 올바르지 않습니다."
        )

    if not verify_password(
        data.password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="닉네임 또는 비밀번호가 올바르지 않습니다."
        )

    if user.is_banned:
        raise HTTPException(
            status_code=403,
            detail="정지된 계정입니다."
        )

    token = create_access_token(user.id)

    return {
        "message": "로그인되었습니다.",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "nickname": user.nickname,
            "is_admin": user.is_admin
        }
    }


@app.get("/me")
def me(
    current_user: User = Depends(get_current_user)
):
    return {
        "id": current_user.id,
        "nickname": current_user.nickname,
        "is_admin": current_user.is_admin
    }


@app.post("/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    allowed_types = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif"
    }

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="JPG, PNG, WEBP, GIF 이미지만 업로드할 수 있습니다."
        )

    data = await file.read()

    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="이미지는 10MB 이하만 업로드할 수 있습니다."
        )

    extension = allowed_types[file.content_type]

    filename = f"{uuid.uuid4().hex}{extension}"

    filepath = os.path.join(
        UPLOAD_DIR,
        filename
    )

    with open(filepath, "wb") as f:
        f.write(data)

    return {
        "message": "이미지가 업로드되었습니다.",
        "image_url": f"/uploads/{filename}"
    }


@app.post("/articles")
def create_article(
    data: ArticleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not data.title.strip():
        raise HTTPException(
            status_code=400,
            detail="기사 제목을 입력하세요."
        )

    article = Article(
        title=data.title.strip(),
        subtitle=data.subtitle,
        author=data.author,
        date=data.date,
        content=data.content,
        image=data.image,
        owner_id=current_user.id
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
            "owner_nickname": current_user.nickname
        }
    }


@app.get("/articles")
def get_articles(
    db: Session = Depends(get_db)
):
    articles = (
        db.query(Article)
        .order_by(Article.id.desc())
        .all()
    )

    result = []

    for article in articles:
        owner = (
            db.query(User)
            .filter(User.id == article.owner_id)
            .first()
        )

        result.append({
            "id": article.id,
            "title": article.title,
            "subtitle": article.subtitle,
            "author": article.author,
            "date": article.date,
            "content": article.content,
            "image": article.image,
            "owner_id": article.owner_id,
            "owner_nickname": (
                owner.nickname
                if owner
                else "알 수 없음"
            )
        })

    return result


@app.get("/articles/{article_id}")
def get_article(
    article_id: int,
    db: Session = Depends(get_db)
):
    article = (
        db.query(Article)
        .filter(Article.id == article_id)
        .first()
    )

    if not article:
        raise HTTPException(
            status_code=404,
            detail="기사를 찾을 수 없습니다."
        )

    owner = (
        db.query(User)
        .filter(User.id == article.owner_id)
        .first()
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
        "owner_nickname": (
            owner.nickname
            if owner
            else "알 수 없음"
        )
    }


@app.put("/articles/{article_id}")
def update_article(
    article_id: int,
    data: ArticleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    article = (
        db.query(Article)
        .filter(Article.id == article_id)
        .first()
    )

    if not article:
        raise HTTPException(
            status_code=404,
            detail="기사를 찾을 수 없습니다."
        )

    if (
        article.owner_id != current_user.id
        and not current_user.is_admin
    ):
        raise HTTPException(
            status_code=403,
            detail="본인의 기사만 수정할 수 있습니다."
        )

    if not data.title.strip():
        raise HTTPException(
            status_code=400,
            detail="기사 제목을 입력하세요."
        )

    article.title = data.title.strip()
    article.subtitle = data.subtitle
    article.author = data.author
    article.date = data.date
    article.content = data.content
    article.image = data.image

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
            "owner_id": article.owner_id
        }
    }


@app.delete("/articles/{article_id}")
def delete_article(
    article_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    article = (
        db.query(Article)
        .filter(Article.id == article_id)
        .first()
    )

    if not article:
        raise HTTPException(
            status_code=404,
            detail="기사를 찾을 수 없습니다."
        )

    if (
        article.owner_id != current_user.id
        and not current_user.is_admin
    ):
        raise HTTPException(
            status_code=403,
            detail="본인의 기사만 삭제할 수 있습니다."
        )

    db.delete(article)
    db.commit()

    return {
        "message": "기사가 삭제되었습니다."
    }


@app.get("/admin/users")
def admin_get_users(
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
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
            "created_at": (
                user.created_at.isoformat()
                if user.created_at
                else None
            )
        }
        for user in users
    ]


@app.put("/admin/users/{user_id}/ban")
def admin_toggle_ban(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="사용자를 찾을 수 없습니다."
        )

    if user.id == admin.id:
        raise HTTPException(
            status_code=400,
            detail="자기 자신은 정지할 수 없습니다."
        )

    user.is_banned = 0 if user.is_banned else 1

    db.commit()
    db.refresh(user)

    return {
        "message": (
            "정지가 해제되었습니다."
            if not user.is_banned
            else "사용자가 정지되었습니다."
        ),
        "user": {
            "id": user.id,
            "nickname": user.nickname,
            "is_banned": user.is_banned
        }
    }


@app.put("/admin/users/{user_id}/admin")
def admin_toggle_admin(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="사용자를 찾을 수 없습니다."
        )

    if user.id == admin.id:
        raise HTTPException(
            status_code=400,
            detail="자기 자신의 관리자 권한은 변경할 수 없습니다."
        )

    user.is_admin = 0 if user.is_admin else 1

    db.commit()
    db.refresh(user)

    return {
        "message": (
            "관리자 권한이 해제되었습니다."
            if not user.is_admin
            else "관리자 권한이 부여되었습니다."
        ),
        "user": {
            "id": user.id,
            "nickname": user.nickname,
            "is_admin": user.is_admin
        }
    }


@app.get("/admin/articles")
def admin_get_articles(
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    articles = (
        db.query(Article)
        .order_by(Article.id.desc())
        .all()
    )

    result = []

    for article in articles:
        owner = (
            db.query(User)
            .filter(User.id == article.owner_id)
            .first()
        )

        result.append({
            "id": article.id,
            "title": article.title,
            "author": article.author,
            "date": article.date,
            "owner_id": article.owner_id,
            "owner_nickname": (
                owner.nickname
                if owner
                else "알 수 없음"
            ),
            "created_at": (
                article.created_at.isoformat()
                if article.created_at
                else None
            )
        })

    return result


# =========================================================
# FRONTEND
# =========================================================

FRONTEND_DIR = os.path.abspath(
    os.path.join(BASE_DIR, "..", "frontend")
)

app.mount(
    "/",
    StaticFiles(
        directory=FRONTEND_DIR,
        html=True
    ),
    name="frontend"
)

