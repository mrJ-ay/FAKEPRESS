import os
import uuid
import json
import urllib.error
import urllib.request
from urllib.parse import urlparse

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Header,
    UploadFile,
    File,
)

from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from pydantic import BaseModel

from sqlalchemy import text
from sqlalchemy.orm import Session

from jose import jwt
from pwdlib import PasswordHash
from supabase import create_client

from database import SessionLocal, engine
from models import Base, User, Article, Comment, OneIDLink


# =========================================================
# DATABASE
# =========================================================

Base.metadata.create_all(bind=engine)


# =========================================================
# BANNED WORD TABLE
# =========================================================

with engine.begin() as connection:
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS banned_words (
                id SERIAL PRIMARY KEY,
                word VARCHAR(100) NOT NULL UNIQUE,
                created_at TIMESTAMP WITH TIME ZONE
            )
            """
        )
    )


# =========================================================
# FASTAPI
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
# CONFIG
# =========================================================

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "change-this-secret-key",
)

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

ONEID_API_URL = os.getenv("ONEID_API_URL", "http://127.0.0.1:8000").rstrip("/")


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "sub": str(user_id),
        "exp": expire,
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# =========================================================
# SUPABASE
# =========================================================

SUPABASE_URL = os.getenv(
    "SUPABASE_URL"
)

SUPABASE_SERVICE_ROLE_KEY = os.getenv(
    "SUPABASE_SERVICE_ROLE_KEY"
)


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


def hash_password(
    password: str,
) -> str:

    return pwd_context.hash(
        password
    )


def verify_password(
    password: str,
    password_hash: str,
) -> bool:

    return pwd_context.verify(
        password,
        password_hash,
    )


# =========================================================
# AUTH — ONEID ONLY
# =========================================================

security = HTTPBearer()


class RejectOneIDRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def verify_oneid_access_token(authorization: str | None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="ONEID 로그인이 필요합니다.")

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="ONEID 로그인이 필요합니다.")

    endpoint = urlparse(ONEID_API_URL)
    if endpoint.scheme != "https" and endpoint.hostname not in {
        "localhost", "127.0.0.1", "::1"
    }:
        raise HTTPException(
            status_code=503,
            detail="운영 환경의 ONEID 주소는 HTTPS여야 합니다.",
        )

    request = urllib.request.Request(
        f"{ONEID_API_URL}/api/auth/me",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )

    try:
        opener = urllib.request.build_opener(RejectOneIDRedirects)
        with opener.open(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise HTTPException(
                status_code=401,
                detail="ONEID 로그인이 만료되었거나 유효하지 않습니다.",
            ) from exc
        raise HTTPException(
            status_code=503,
            detail="ONEID 계정 확인에 실패했습니다.",
        ) from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="ONEID 서버에 연결할 수 없습니다.",
        ) from exc

    if not isinstance(payload, dict) or not payload.get("id"):
        raise HTTPException(
            status_code=401,
            detail="ONEID 계정을 확인할 수 없습니다.",
        )

    return payload


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_or_create_oneid_user(oneid_user: dict, db: Session) -> User:
    oneid_user_id = str(oneid_user["id"])
    nickname = str(oneid_user.get("nickname") or "").strip()

    if not nickname or len(nickname) > 20:
        raise HTTPException(
            status_code=400,
            detail="ONEID 닉네임을 1~20자로 설정해 주세요.",
        )

    link = (
        db.query(OneIDLink)
        .filter(OneIDLink.oneid_user_id == oneid_user_id)
        .first()
    )

    user = (
        db.query(User).filter(User.id == link.user_id).first()
        if link else None
    )

    # 기존 FAKEPRESS 계정과는 자동으로 연결하지 않는다.
    # 동일한 ONEID 사용자는 이후 로그인에서도 같은 연결을 사용한다.
    if user is None:
        base = nickname[:20]
        candidate = base

        while db.query(User).filter(User.nickname == candidate).first():
            suffix = "_" + uuid.uuid4().hex[:6]
            candidate = nickname[:20 - len(suffix)] + suffix

        user = User(
            nickname=candidate,
            password_hash=hash_password(uuid.uuid4().hex + uuid.uuid4().hex),
            is_admin=1 if oneid_user.get("is_admin") else 0,
            is_banned=0,
        )

        try:
            db.add(user)
            db.flush()
            db.add(OneIDLink(
                oneid_user_id=oneid_user_id,
                user_id=user.id,
            ))
            db.commit()
            db.refresh(user)
        except Exception as exc:
            db.rollback()
            # 다른 요청에서 같은 ONEID 계정을 먼저 생성했을 수 있다.
            link = (
                db.query(OneIDLink)
                .filter(OneIDLink.oneid_user_id == oneid_user_id)
                .first()
            )
            if link:
                user = db.query(User).filter(User.id == link.user_id).first()
            if user is None:
                raise HTTPException(
                    status_code=409,
                    detail="FAKEPRESS 계정을 생성하지 못했습니다. 다시 로그인해 주세요.",
                ) from exc

    if user.is_banned == 1:
        raise HTTPException(
            status_code=403,
            detail="이 사이트에서 이용 정지된 계정입니다.",
        )

    # 관리자 권한은 ONEID에서 확인한 결과로 동기화한다.
    expected_admin = 1 if oneid_user.get("is_admin") else 0
    if user.is_admin != expected_admin:
        user.is_admin = expected_admin
        db.commit()

    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    token = credentials.credentials
    user = None

    # 1. FAKEPRESS 자체 발급 JWT 검증 시도
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str = payload.get("sub")
        if user_id_str and str(user_id_str).isdigit():
            user = db.query(User).filter(User.id == int(user_id_str)).first()
    except Exception:
        user = None

    # 2. 자체 JWT 디코딩 실패 시 ONEID SSO 토큰으로 검증 시도 (하위 호환)
    if user is None:
        try:
            oneid_user = verify_oneid_access_token(f"Bearer {token}")
            user = get_or_create_oneid_user(oneid_user, db)
        except Exception:
            raise HTTPException(
                status_code=401,
                detail="로그인이 만료되었거나 유효하지 않습니다.",
            )

    if not user:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다.")

    if user.is_banned == 1:
        raise HTTPException(
            status_code=403,
            detail="이 사이트에서 이용이 정지된 계정입니다.",
        )

    return user


def get_admin_user(
    current_user: User = Depends(get_current_user),
):
    if current_user.is_admin != 1:
        raise HTTPException(
            status_code=403,
            detail="ONEID 관리자 권한이 필요합니다.",
        )
    return current_user


# =========================================================
# REQUEST MODELS
# =========================================================

class RegisterRequest(BaseModel):

    nickname: str
    password: str


class LoginRequest(BaseModel):

    nickname: str
    password: str


class OneIDCompleteRequest(BaseModel):
    legacy_nickname: str | None = None
    legacy_password: str | None = None
    create_new: bool = False


class ArticleRequest(BaseModel):

    title: str
    subtitle: str = ""
    author: str = ""
    date: str = ""
    content: str = ""
    image: str | None = None


class CommentRequest(BaseModel):

    content: str


class BannedWordRequest(BaseModel):

    word: str


# =========================================================
# ROOT
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
    raise HTTPException(status_code=410, detail="ONEID 로그인으로 통합되었습니다.")

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
        .filter(
            User.nickname == nickname
        )
        .first()
    )

    if existing:

        raise HTTPException(
            status_code=400,
            detail="이미 존재하는 닉네임입니다.",
        )

    user = User(
        nickname=nickname,
        password_hash=hash_password(
            password
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
            "is_admin": user.is_admin,
            "is_banned": user.is_banned,
        },
    }



# =========================================================
# LOGIN - ONEID ONLY
# =========================================================

@app.post("/auth/login")
def login_disabled():
    raise HTTPException(
        status_code=410,
        detail="로그인은 ONEID를 이용해 주세요.",
    )


@app.post("/auth/oneid/complete")
def complete_oneid_login(
    authorization: str | None = Header(
        default=None,
        alias="Authorization",
    ),
    db: Session = Depends(get_db),
):
    # ONEID 서버에서 토큰을 검증하고 사용자 정보를 가져온다.
    oneid_user = verify_oneid_access_token(authorization)

    # FAKEPRESS 사용자 계정을 조회하거나 생성한다.
    user = get_or_create_oneid_user(oneid_user, db)

    # 정지된 계정은 로그인할 수 없다.
    if user.is_banned == 1:
        raise HTTPException(
            status_code=403,
            detail="이 사이트에서 이용이 정지된 계정입니다.",
        )

    # 반드시 FAKEPRESS 자체 JWT를 발급한다.
    # ONEID access token을 반환하면 안 된다.
    token = create_access_token(user.id)

    return {
        "message": "ONEID 로그인이 완료되었습니다.",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "nickname": user.nickname,
            "is_admin": user.is_admin == 1,
            "is_banned": user.is_banned == 1,
        },
    }




# =========================================================
# CURRENT USER
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


@app.post("/auth/link-oneid")
def link_oneid(
    current_user: User = Depends(get_current_user),
    oneid_authorization: str | None = Header(default=None, alias="X-ONEID-Authorization"),
    db: Session = Depends(get_db),
):
    """Link an authenticated local account to its authenticated ONEID account."""
    oneid_user = verify_oneid_access_token(oneid_authorization)
    oneid_user_id = str(oneid_user["id"])
    nickname = str(oneid_user.get("nickname") or "").strip()
    if not nickname or len(nickname) > 20:
        raise HTTPException(status_code=409, detail="ONEID 닉네임은 1~20자로 맞춘 뒤 연결해 주세요.")

    if db.query(OneIDLink).filter(OneIDLink.user_id == current_user.id).first():
        raise HTTPException(status_code=409, detail="이 사이트 계정은 이미 ONEID에 연결되어 있습니다.")
    if db.query(OneIDLink).filter(OneIDLink.oneid_user_id == oneid_user_id).first():
        raise HTTPException(status_code=409, detail="이 ONEID 계정은 이미 다른 사이트 계정에 연결되어 있습니다.")

    nickname_owner = db.query(User).filter(User.nickname == nickname, User.id != current_user.id).first()
    if nickname_owner:
        raise HTTPException(status_code=409, detail="ONEID 닉네임이 이 사이트의 다른 계정에서 사용 중입니다.")

    current_user.nickname = nickname
    current_user.is_admin = 1 if oneid_user.get("is_admin") else 0
    db.add(OneIDLink(oneid_user_id=oneid_user_id, user_id=current_user.id))
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="계정 연결을 저장하지 못했습니다. 이미 연결되었는지 새로고침해 확인해 주세요.") from exc

    return {"message": "ONEID 계정이 연결되었습니다.", "user": {"id": current_user.id, "nickname": nickname, "oneid_user_id": oneid_user_id}}


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
                "content-type":
                    file.content_type,
                "upsert": "false",
            },
        )

        public_url = (
            supabase.storage
            .from_(bucket_name)
            .get_public_url(
                filename
            )
        )

        return {
            "message":
                "이미지가 업로드되었습니다.",
            "image":
                public_url,
            "image_url":
                public_url,
        }

    except Exception as error:

        print(
            "IMAGE UPLOAD ERROR:",
            error
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
# GET ARTICLE
# =========================================================

@app.get("/articles/{article_id}")
def get_article(
    article_id: int,
    db: Session = Depends(get_db),
):

    article = (
        db.query(Article)
        .filter(
            Article.id == article_id
        )
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
# =========================================================

@app.post("/articles")
def create_article(
    request: ArticleRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):

    # -----------------------------------------------------
    # 금지어 검사
    # -----------------------------------------------------

    banned_word = find_banned_word(
        db,
        request.title,
        request.subtitle,
        request.content,
    )

    if banned_word:

        raise HTTPException(
            status_code=400,
            detail=(
                f'금지어 "{banned_word}"가 포함되어 있어 '
                "기사를 등록할 수 없습니다."
            ),
        )

    # -----------------------------------------------------
    # 기사 작성 쿨타임
    # -----------------------------------------------------

    now = datetime.now(
        timezone.utc
    )

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
        .filter(
            Article.id == article_id
        )
        .first()
    )

    if not article:

        raise HTTPException(
            status_code=404,
            detail="기사를 찾을 수 없습니다.",
        )

    if (
        article.owner_id
        != current_user.id
        and current_user.is_admin != 1
    ):

        raise HTTPException(
            status_code=403,
            detail="수정 권한이 없습니다.",
        )

    # -----------------------------------------------------
    # 금지어 검사
    # -----------------------------------------------------

    banned_word = find_banned_word(
        db,
        request.title,
        request.subtitle,
        request.content,
    )

    if banned_word:

        raise HTTPException(
            status_code=400,
            detail=(
                f'금지어 "{banned_word}"가 포함되어 있어 '
                "기사를 수정할 수 없습니다."
            ),
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
        .filter(
            Article.id == article_id
        )
        .first()
    )

    if not article:

        raise HTTPException(
            status_code=404,
            detail="기사를 찾을 수 없습니다.",
        )

    if (
        article.owner_id
        != current_user.id
        and current_user.is_admin != 1
    ):

        raise HTTPException(
            status_code=403,
            detail="삭제 권한이 없습니다.",
        )

    db.query(Comment).filter(
        Comment.article_id == article_id
    ).delete(
        synchronize_session=False
    )

    db.delete(article)

    db.commit()

    return {
        "message": "기사가 삭제되었습니다."
    }


# =========================================================
# GET COMMENTS
# =========================================================

@app.get("/articles/{article_id}/comments")
def get_comments(
    article_id: int,
    db: Session = Depends(get_db),
):

    article = (
        db.query(Article)
        .filter(
            Article.id == article_id
        )
        .first()
    )

    if not article:

        raise HTTPException(
            status_code=404,
            detail="기사를 찾을 수 없습니다.",
        )

    comments = (
        db.query(Comment, User)
        .join(
            User,
            Comment.owner_id == User.id,
        )
        .filter(
            Comment.article_id
            == article_id
        )
        .order_by(
            Comment.created_at.asc()
        )
        .all()
    )

    return [
        {
            "id": comment.id,
            "content": comment.content,
            "article_id":
                comment.article_id,
            "owner_id":
                comment.owner_id,
            "nickname":
                user.nickname,
            "created_at":
                comment.created_at,
        }
        for comment, user in comments
    ]


# =========================================================
# CREATE COMMENT
# =========================================================

@app.post("/articles/{article_id}/comments")
def create_comment(
    article_id: int,
    request: CommentRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):

    article = (
        db.query(Article)
        .filter(
            Article.id == article_id
        )
        .first()
    )

    if not article:

        raise HTTPException(
            status_code=404,
            detail="기사를 찾을 수 없습니다.",
        )

    content = request.content.strip()

    if not content:

        raise HTTPException(
            status_code=400,
            detail="댓글 내용을 입력해주세요.",
        )

    if len(content) > 1000:

        raise HTTPException(
            status_code=400,
            detail="댓글은 1000자 이하로 입력해주세요.",
        )

    # -----------------------------------------------------
    # 최근 댓글 조회
    # -----------------------------------------------------

    last_comment = (
        db.query(Comment)
        .filter(
            Comment.owner_id
            == current_user.id
        )
        .order_by(
            Comment.created_at.desc()
        )
        .first()
    )

    now = datetime.now(
        timezone.utc
    )

    # -----------------------------------------------------
    # 댓글 10초 쿨타임
    # -----------------------------------------------------

    if (
        last_comment
        and last_comment.created_at
    ):

        last_time = (
            last_comment.created_at
        )

        if last_time.tzinfo is None:

            last_time = last_time.replace(
                tzinfo=timezone.utc
            )

        elapsed = (
            now - last_time
        )

        cooldown = timedelta(
            seconds=10
        )

        if elapsed < cooldown:

            remaining_seconds = int(
                (
                    cooldown - elapsed
                ).total_seconds()
            )

            raise HTTPException(
                status_code=429,
                detail=(
                    "댓글 도배 방지를 위해 "
                    f"{remaining_seconds}초 후 "
                    "다시 작성할 수 있습니다."
                ),
            )

    comment = Comment(
        content=content,
        article_id=article_id,
        owner_id=current_user.id,
    )

    db.add(comment)

    db.commit()

    db.refresh(comment)

    return {
        "message": "댓글이 작성되었습니다.",
        "comment": {
            "id": comment.id,
            "content": comment.content,
            "article_id":
                comment.article_id,
            "owner_id":
                comment.owner_id,
            "nickname":
                current_user.nickname,
            "created_at":
                comment.created_at,
        },
    }


# =========================================================
# DELETE COMMENT
# =========================================================

@app.delete("/comments/{comment_id}")
def delete_comment(
    comment_id: int,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):

    comment = (
        db.query(Comment)
        .filter(
            Comment.id == comment_id
        )
        .first()
    )

    if not comment:

        raise HTTPException(
            status_code=404,
            detail="댓글을 찾을 수 없습니다.",
        )

    if (
        comment.owner_id
        != current_user.id
        and current_user.is_admin != 1
    ):

        raise HTTPException(
            status_code=403,
            detail="댓글 삭제 권한이 없습니다.",
        )

    db.delete(comment)

    db.commit()

    return {
        "message": "댓글이 삭제되었습니다."
    }


# =========================================================
# ADMIN USERS
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
# MAKE ADMIN
# =========================================================

@app.post("/admin/make-admin/{user_id}")
def make_admin(
    user_id: int,
    admin: User = Depends(
        get_admin_user
    ),
    db: Session = Depends(get_db),
):
    raise HTTPException(status_code=410, detail="전체 관리자 권한은 ONEID에서 관리합니다.")

    user = (
        db.query(User)
        .filter(
            User.id == user_id
        )
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
        "message":
            "관리자로 지정되었습니다.",
        "user": {
            "id": user.id,
            "nickname": user.nickname,
            "is_admin": user.is_admin,
        },
    }


# =========================================================
# REMOVE ADMIN
# =========================================================

@app.post("/admin/remove-admin/{user_id}")
def remove_admin(
    user_id: int,
    admin: User = Depends(
        get_admin_user
    ),
    db: Session = Depends(get_db),
):
    raise HTTPException(status_code=410, detail="전체 관리자 권한은 ONEID에서 관리합니다.")

    user = (
        db.query(User)
        .filter(
            User.id == user_id
        )
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
            detail="자기 자신의 관리자 권한은 해제할 수 없습니다.",
        )

    user.is_admin = 0

    db.commit()

    db.refresh(user)

    return {
        "message":
            "관리자 권한이 해제되었습니다.",
        "user": {
            "id": user.id,
            "nickname": user.nickname,
            "is_admin": user.is_admin,
        },
    }


# =========================================================
# BAN USER
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
        .filter(
            User.id == user_id
        )
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
        "message":
            "사용자가 정지되었습니다.",
        "user": {
            "id": user.id,
            "nickname": user.nickname,
            "is_banned": user.is_banned,
        },
    }


# =========================================================
# UNBAN USER
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
        .filter(
            User.id == user_id
        )
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
        "message":
            "사용자 정지가 해제되었습니다.",
        "user": {
            "id": user.id,
            "nickname": user.nickname,
            "is_banned": user.is_banned,
        },
    }


# =========================================================
# ADMIN BANNED WORDS
# =========================================================

@app.get("/admin/banned-words")
def admin_get_banned_words(
    admin: User = Depends(
        get_admin_user
    ),
    db: Session = Depends(get_db),
):

    rows = get_banned_words(db)

    return [
        {
            "id": row["id"],
            "word": row["word"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


# =========================================================
# ADD BANNED WORD
# =========================================================

@app.post("/admin/banned-words")
def admin_add_banned_word(
    request: BannedWordRequest,
    admin: User = Depends(
        get_admin_user
    ),
    db: Session = Depends(get_db),
):

    word = request.word.strip()

    if not word:

        raise HTTPException(
            status_code=400,
            detail="금지어를 입력해주세요.",
        )

    if len(word) > 100:

        raise HTTPException(
            status_code=400,
            detail="금지어는 100자 이하로 입력해주세요.",
        )

    # -----------------------------------------------------
    # 중복 검사
    # -----------------------------------------------------

    existing_rows = get_banned_words(db)

    for row in existing_rows:

        existing_word = (
            row["word"] or ""
        ).strip()

        if (
            existing_word.casefold()
            == word.casefold()
        ):

            raise HTTPException(
                status_code=400,
                detail="이미 등록된 금지어입니다.",
            )

    # -----------------------------------------------------
    # 금지어 저장
    # -----------------------------------------------------

    try:

        db.execute(
            text(
                """
                INSERT INTO banned_words
                (
                    word,
                    created_at
                )
                VALUES
                (
                    :word,
                    :created_at
                )
                """
            ),
            {
                "word": word,
                "created_at":
                    datetime.now(
                        timezone.utc
                    ),
            },
        )

        db.commit()

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=400,
            detail="금지어 저장에 실패했습니다.",
        )

    # -----------------------------------------------------
    # 기존 기사 자동 삭제
    # -----------------------------------------------------

    deleted_count = (
        delete_articles_containing_word(
            db,
            word,
        )
    )

    db.commit()

    return {
        "message": (
            f'"{word}" 금지어가 등록되었습니다.'
        ),
        "word": word,
        "deleted_articles":
            deleted_count,
    }


# =========================================================
# DELETE BANNED WORD
# =========================================================

@app.delete("/admin/banned-words/{word_id}")
def admin_delete_banned_word(
    word_id: int,
    admin: User = Depends(
        get_admin_user
    ),
    db: Session = Depends(get_db),
):

    row = db.execute(
        text(
            """
            SELECT
                id,
                word
            FROM banned_words
            WHERE id = :id
            """
        ),
        {
            "id": word_id
        },
    ).mappings().first()

    if not row:

        raise HTTPException(
            status_code=404,
            detail="금지어를 찾을 수 없습니다.",
        )

    db.execute(
        text(
            """
            DELETE FROM banned_words
            WHERE id = :id
            """
        ),
        {
            "id": word_id
        },
    )

    db.commit()

    return {
        "message": (
            f'"{row["word"]}" 금지어가 삭제되었습니다.'
        )
    }


# =========================================================
# ADMIN ARTICLES
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
# ADMIN DELETE ARTICLE
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
        .filter(
            Article.id == article_id
        )
        .first()
    )

    if not article:

        raise HTTPException(
            status_code=404,
            detail="기사를 찾을 수 없습니다.",
        )

    db.query(Comment).filter(
        Comment.article_id == article_id
    ).delete(
        synchronize_session=False
    )

    db.delete(article)

    db.commit()

    return {
        "message": "기사가 삭제되었습니다."
    }


# =========================================================
# ADMIN DELETE ALL ARTICLES
# =========================================================

@app.delete("/admin/articles")
def admin_delete_all_articles(
    admin: User = Depends(
        get_admin_user
    ),
    db: Session = Depends(get_db),
):

    articles = (
        db.query(Article)
        .all()
    )

    deleted_count = len(
        articles
    )

    db.query(Comment).delete(
        synchronize_session=False
    )

    db.query(Article).delete(
        synchronize_session=False
    )

    db.commit()

    return {
        "message":
            "모든 뉴스가 삭제되었습니다.",
        "deleted_count":
            deleted_count,
    }
