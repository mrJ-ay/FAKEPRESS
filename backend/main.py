import os
import uuid
from datetime import datetime, timedelta

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


# =========================================================
# 기본 설정
# =========================================================

app = FastAPI(
    title="FAKEPRESS API",
    description="FAKEPRESS backend API",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# JWT 설정
# =========================================================

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "dev-only-change-me"
)

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24


security = HTTPBearer()


# =========================================================
# 업로드 폴더
# =========================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

UPLOAD_DIR = os.path.join(
    BASE_DIR,
    "uploads"
)

os.makedirs(
    UPLOAD_DIR,
    exist_ok=True
)


app.mount(
    "/uploads",
    StaticFiles(directory=UPLOAD_DIR),
    name="uploads"
)


# =========================================================
# DB 테이블 생성
# =========================================================

Base.metadata.create_all(
    bind=engine
)


# =========================================================
# Pydantic 모델
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
    image: str = ""


# =========================================================
# JWT
# =========================================================

def create_access_token(
    user_id: int
):

    expire = datetime.utcnow() + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
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


# =========================================================
# 현재 사용자
# =========================================================

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

        if user_id is None:
            raise HTTPException(
                status_code=401,
                detail="유효하지 않은 토큰입니다."
            )

        user_id = int(user_id)

    except (JWTError, ValueError):

        raise HTTPException(
            status_code=401,
            detail="유효하지 않은 토큰입니다."
        )

    user = db.query(User).filter(
        User.id == user_id
    ).first()

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


# =========================================================
# 관리자 확인
# =========================================================

def get_admin_user(
    current_user: User = Depends(get_current_user)
):

    if current_user.is_admin != 1:

        raise HTTPException(
            status_code=403,
            detail="관리자 권한이 필요합니다."
        )

    return current_user


# =========================================================
# 기본
# =========================================================

@app.get("/")
def root():

    return {
        "message": "FAKEPRESS API is running"
    }


# =========================================================
# 회원가입
# =========================================================

@app.post("/register")
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db)
):

    existing_user = db.query(User).filter(
        User.nickname == data.nickname
    ).first()

    if existing_user:

        raise HTTPException(
            status_code=400,
            detail="이미 존재하는 닉네임입니다."
        )

    if len(data.nickname.strip()) == 0:

        raise HTTPException(
            status_code=400,
            detail="닉네임을 입력해주세요."
        )

    if len(data.password) < 4:

        raise HTTPException(
            status_code=400,
            detail="비밀번호는 4자 이상이어야 합니다."
        )

    new_user = User(
        nickname=data.nickname,
        password_hash=hash_password(data.password),
        is_admin=0,
        is_banned=0
    )

    db.add(new_user)

    db.commit()

    db.refresh(new_user)

    return {
        "message": "회원가입이 완료되었습니다.",
        "user": {
            "id": new_user.id,
            "nickname": new_user.nickname
        }
    }


# =========================================================
# 로그인
# =========================================================

@app.post("/login")
def login(
    data: LoginRequest,
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(
        User.nickname == data.nickname
    ).first()

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

    access_token = create_access_token(
        user.id
    )

    return {
        "message": "로그인되었습니다.",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "nickname": user.nickname,
            "is_admin": user.is_admin
        }
    }


# =========================================================
# 내 정보
# =========================================================

@app.get("/me")
def get_me(
    current_user: User = Depends(get_current_user)
):

    return {
        "id": current_user.id,
        "nickname": current_user.nickname,
        "is_admin": current_user.is_admin,
        "is_banned": current_user.is_banned
    }


# =========================================================
# 이미지 업로드
# =========================================================

@app.post("/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):

    if not file.content_type:

        raise HTTPException(
            status_code=400,
            detail="파일 형식을 확인할 수 없습니다."
        )

    if not file.content_type.startswith("image/"):

        raise HTTPException(
            status_code=400,
            detail="이미지 파일만 업로드할 수 있습니다."
        )

    extension = ""

    if "." in file.filename:

        extension = os.path.splitext(
            file.filename
        )[1].lower()

    filename = (
        f"{uuid.uuid4().hex}"
        f"{extension}"
    )

    file_path = os.path.join(
        UPLOAD_DIR,
        filename
    )

    with open(
        file_path,
        "wb"
    ) as buffer:

        buffer.write(
            await file.read()
        )

    return {
        "message": "이미지가 업로드되었습니다.",
        "filename": filename,
        "url": f"/uploads/{filename}"
    }


# =========================================================
# 글 작성
# =========================================================

@app.post("/articles")
def create_article(
    data: ArticleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    article = Article(
        title=data.title,
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
        "message": "글이 저장되었습니다.",
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


# =========================================================
# 글 목록
# =========================================================

@app.get("/articles")
def get_articles(
    db: Session = Depends(get_db)
):

    articles = (
        db.query(Article)
        .order_by(Article.id.desc())
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
            "updated_at": article.updated_at
        }
        for article in articles
    ]


# =========================================================
# 글 하나
# =========================================================

@app.get("/articles/{article_id}")
def get_article(
    article_id: int,
    db: Session = Depends(get_db)
):

    article = db.query(Article).filter(
        Article.id == article_id
    ).first()

    if not article:

        raise HTTPException(
            status_code=404,
            detail="글을 찾을 수 없습니다."
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
        "updated_at": article.updated_at
    }


# =========================================================
# 글 수정
# =========================================================

@app.put("/articles/{article_id}")
def update_article(
    article_id: int,
    data: ArticleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    article = db.query(Article).filter(
        Article.id == article_id
    ).first()

    if not article:

        raise HTTPException(
            status_code=404,
            detail="글을 찾을 수 없습니다."
        )

    if (
        article.owner_id != current_user.id
        and current_user.is_admin != 1
    ):

        raise HTTPException(
            status_code=403,
            detail="수정 권한이 없습니다."
        )

    article.title = data.title
    article.subtitle = data.subtitle
    article.author = data.author
    article.date = data.date
    article.content = data.content
    article.image = data.image

    db.commit()

    db.refresh(article)

    return {
        "message": "글이 수정되었습니다.",
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


# =========================================================
# 글 삭제
# =========================================================

@app.delete("/articles/{article_id}")
def delete_article(
    article_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    article = db.query(Article).filter(
        Article.id == article_id
    ).first()

    if not article:

        raise HTTPException(
            status_code=404,
            detail="글을 찾을 수 없습니다."
        )

    if (
        article.owner_id != current_user.id
        and current_user.is_admin != 1
    ):

        raise HTTPException(
            status_code=403,
            detail="삭제 권한이 없습니다."
        )

    db.delete(article)

    db.commit()

    return {
        "message": "글이 삭제되었습니다."
    }


# =========================================================
# 관리자 - 사용자 목록
# =========================================================

@app.get("/admin/users")
def admin_get_users(
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
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
            "created_at": user.created_at
        }
        for user in users
    ]


# =========================================================
# 관리자 - 관리자 승격
# =========================================================

@app.post("/admin/make-admin/{user_id}")
def make_admin(
    user_id: int,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not user:

        raise HTTPException(
            status_code=404,
            detail="사용자를 찾을 수 없습니다."
        )

    user.is_admin = 1

    db.commit()

    db.refresh(user)

    return {
        "message": "관리자로 설정되었습니다.",
        "user": {
            "id": user.id,
            "nickname": user.nickname,
            "is_admin": user.is_admin
        }
    }


# =========================================================
# 관리자 - 관리자 권한 해제
# =========================================================

@app.post("/admin/remove-admin/{user_id}")
def remove_admin(
    user_id: int,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not user:

        raise HTTPException(
            status_code=404,
            detail="사용자를 찾을 수 없습니다."
        )

    if user.id == admin_user.id:

        raise HTTPException(
            status_code=400,
            detail="자기 자신의 관리자 권한은 해제할 수 없습니다."
        )

    user.is_admin = 0

    db.commit()

    db.refresh(user)

    return {
        "message": "관리자 권한이 해제되었습니다.",
        "user": {
            "id": user.id,
            "nickname": user.nickname,
            "is_admin": user.is_admin
        }
    }


# =========================================================
# 관리자 - 사용자 정지
# =========================================================

@app.post("/admin/users/{user_id}/ban")
def ban_user(
    user_id: int,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not user:

        raise HTTPException(
            status_code=404,
            detail="사용자를 찾을 수 없습니다."
        )

    if user.id == admin_user.id:

        raise HTTPException(
            status_code=400,
            detail="자기 자신을 정지할 수 없습니다."
        )

    user.is_banned = 1

    db.commit()

    db.refresh(user)

    return {
        "message": "사용자가 정지되었습니다.",
        "user": {
            "id": user.id,
            "nickname": user.nickname,
            "is_banned": user.is_banned
        }
    }


# =========================================================
# 관리자 - 사용자 정지 해제
# =========================================================

@app.post("/admin/users/{user_id}/unban")
def unban_user(
    user_id: int,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not user:

        raise HTTPException(
            status_code=404,
            detail="사용자를 찾을 수 없습니다."
        )

    user.is_banned = 0

    db.commit()

    db.refresh(user)

    return {
        "message": "사용자 정지가 해제되었습니다.",
        "user": {
            "id": user.id,
            "nickname": user.nickname,
            "is_banned": user.is_banned
        }
    }


# =========================================================
# 관리자 - 전체 글 목록
# =========================================================

@app.get("/admin/articles")
def admin_get_articles(
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):

    articles = (
        db.query(Article)
        .order_by(Article.id.desc())
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
            "updated_at": article.updated_at
        }
        for article in articles
    ]


# =========================================================
# 관리자 - 글 삭제
# =========================================================

@app.delete("/admin/articles/{article_id}")
def admin_delete_article(
    article_id: int,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):

    article = db.query(Article).filter(
        Article.id == article_id
    ).first()

    if not article:

        raise HTTPException(
            status_code=404,
            detail="글을 찾을 수 없습니다."
        )

    db.delete(article)

    db.commit()

    return {
        "message": "관리자 권한으로 글이 삭제되었습니다."
    }