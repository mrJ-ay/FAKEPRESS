// ============================================================
// FAKEPRESS FRONTEND
// ============================================================


// ============================================================
// API
// ============================================================

const API_URL = "http://127.0.0.1:8000";


// ============================================================
// DOM
// ============================================================

const loginPage =
    document.getElementById("loginPage");

const editorPage =
    document.getElementById("editorPage");

const articlesPage =
    document.getElementById("articlesPage");

const viewPage =
    document.getElementById("viewPage");


const loginButton =
    document.getElementById("loginButton");

const adminButton =
    document.getElementById("adminButton");

const userInfo =
    document.getElementById("userInfo");

const loggedInUser =
    document.getElementById("loggedInUser");


// 로그인

const loginNickname =
    document.getElementById("loginNickname");

const loginPassword =
    document.getElementById("loginPassword");


// 기사 입력

const titleInput =
    document.getElementById("title");

const subtitleInput =
    document.getElementById("subtitle");

const authorInput =
    document.getElementById("author");

const dateInput =
    document.getElementById("date");

const imageInput =
    document.getElementById("image");

const contentInput =
    document.getElementById("content");


// 기사 목록

const articleList =
    document.getElementById("articleList");

const searchInput =
    document.getElementById("search");


// 미리보기

const previewTitle =
    document.getElementById("previewTitle");

const previewSubtitle =
    document.getElementById("previewSubtitle");

const previewAuthor =
    document.getElementById("previewAuthor");

const previewDate =
    document.getElementById("previewDate");

const previewImage =
    document.getElementById("previewImage");

const previewContent =
    document.getElementById("previewContent");


// 기사 보기

const viewTitle =
    document.getElementById("viewTitle");

const viewSubtitle =
    document.getElementById("viewSubtitle");

const viewAuthor =
    document.getElementById("viewAuthor");

const viewDate =
    document.getElementById("viewDate");

const viewImage =
    document.getElementById("viewImage");

const viewContent =
    document.getElementById("viewContent");


// 편집 제목

const editorTitle =
    document.getElementById("editorTitle");


// ============================================================
// 상태
// ============================================================

let currentUser = null;

let editingId = null;

let currentArticleId = null;

let imageData = "";

let articles = [];

let imageUploading = false;


// ============================================================
// 이미지 URL 처리
// ============================================================
//
// 기존 Base64 이미지:
// data:image/... 로 시작하므로 그대로 사용
//
// 새 업로드 이미지:
// /uploads/xxxxx.jpg 형태이므로
// http://127.0.0.1:8000/uploads/xxxxx.jpg 로 변환
//
// 혹시 완전한 URL이 들어오면 그대로 사용
// ============================================================

function getImageUrl(
    image
) {

    if (!image) {

        return "";

    }


    if (
        image.startsWith("data:")
    ) {

        return image;

    }


    if (
        image.startsWith("http://") ||
        image.startsWith("https://")
    ) {

        return image;

    }


    return (
        `${API_URL}` +
        `${image.startsWith("/") ? "" : "/"}` +
        `${image}`
    );

}


// ============================================================
// 인증 정보
// ============================================================

function loadCurrentUser() {

    const savedUser =
        localStorage.getItem(
            "fakepress_current_user"
        );

    const savedToken =
        localStorage.getItem(
            "fakepress_token"
        );


    if (
        savedUser &&
        savedToken
    ) {

        try {

            currentUser =
                JSON.parse(
                    savedUser
                );

        } catch {

            currentUser = null;

            localStorage.removeItem(
                "fakepress_current_user"
            );

            localStorage.removeItem(
                "fakepress_token"
            );

        }

    } else {

        currentUser = null;

    }


    updateLoginUI();

}


// ============================================================
// 로그인 UI
// ============================================================

function updateLoginUI() {

    if (currentUser) {

        loginButton.hidden = true;

        userInfo.hidden = false;

        loggedInUser.textContent =
            `${currentUser.nickname}님 로그인됨`;


        // 관리자 계정이면 관리자 버튼 표시
        if (
            Number(currentUser.is_admin) === 1
        ) {

            adminButton.style.display =
                "inline-block";

        } else {

            adminButton.style.display =
                "none";

        }

    } else {

        loginButton.hidden = false;

        userInfo.hidden = true;

        loggedInUser.textContent = "";


        // 로그아웃 상태에서는 관리자 버튼 숨김
        adminButton.style.display =
            "none";

    }

}


// ============================================================
// 토큰
// ============================================================

function getToken() {

    return localStorage.getItem(
        "fakepress_token"
    );

}


// ============================================================
// 인증 헤더
// ============================================================

function getAuthHeaders() {

    const token =
        getToken();


    if (!token) {

        return {};

    }


    return {

        "Authorization":
            `Bearer ${token}`

    };

}


// ============================================================
// 페이지 숨기기
// ============================================================

function hideAllPages() {

    loginPage.hidden = true;

    editorPage.hidden = true;

    articlesPage.hidden = true;

    viewPage.hidden = true;

}


// ============================================================
// 로그인 페이지
// ============================================================

function showLogin() {

    hideAllPages();

    loginPage.hidden = false;

}


// ============================================================
// 기사 작성 페이지
// ============================================================

function showEditor() {

    if (!currentUser) {

        alert(
            "로그인이 필요합니다."
        );

        showLogin();

        return;

    }


    hideAllPages();

    editorPage.hidden = false;


    updatePreview();

}


// ============================================================
// 기사 목록 페이지
// ============================================================

async function showArticles() {

    hideAllPages();

    articlesPage.hidden = false;


    await loadArticles();

}


// ============================================================
// 회원가입
// ============================================================

async function registerUser() {

    const nickname =
        loginNickname.value.trim();

    const password =
        loginPassword.value;


    if (!nickname || !password) {

        alert(
            "닉네임과 비밀번호를 입력하세요."
        );

        return;

    }


    try {

        const response =
            await fetch(
                `${API_URL}/register`,
                {

                    method: "POST",

                    headers: {

                        "Content-Type":
                            "application/json"

                    },

                    body: JSON.stringify({

                        nickname:
                            nickname,

                        password:
                            password

                    })

                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.detail ||
                "회원가입에 실패했습니다."
            );

        }


        alert(
            "회원가입이 완료되었습니다."
        );


        loginPassword.value = "";


    } catch (error) {

        console.error(error);

        alert(
            error.message
        );

    }

}


// ============================================================
// 로그인
// ============================================================

async function login() {

    const nickname =
        loginNickname.value.trim();

    const password =
        loginPassword.value;


    if (!nickname || !password) {

        alert(
            "닉네임과 비밀번호를 입력하세요."
        );

        return;

    }


    try {

        const response =
            await fetch(
                `${API_URL}/login`,
                {

                    method: "POST",

                    headers: {

                        "Content-Type":
                            "application/json"

                    },

                    body: JSON.stringify({

                        nickname:
                            nickname,

                        password:
                            password

                    })

                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.detail ||
                "로그인에 실패했습니다."
            );

        }


        currentUser =
            data.user;


        localStorage.setItem(
            "fakepress_current_user",
            JSON.stringify(
                currentUser
            )
        );


        localStorage.setItem(
            "fakepress_token",
            data.access_token
        );


        updateLoginUI();


        loginNickname.value = "";

        loginPassword.value = "";


        alert(
            "로그인되었습니다."
        );


        showEditor();


    } catch (error) {

        console.error(error);

        alert(
            error.message
        );

    }

}


// ============================================================
// 로그아웃
// ============================================================

function logout() {

    currentUser = null;

    editingId = null;

    currentArticleId = null;

    imageData = "";

    imageUploading = false;


    localStorage.removeItem(
        "fakepress_current_user"
    );


    localStorage.removeItem(
        "fakepress_token"
    );


    updateLoginUI();


    showLogin();

}


// ============================================================
// 이미지 업로드
// ============================================================

async function uploadImage(
    file
) {

    if (!currentUser) {

        throw new Error(
            "로그인이 필요합니다."
        );

    }


    if (!file) {

        return "";

    }


    if (
        !file.type.startsWith(
            "image/"
        )
    ) {

        throw new Error(
            "이미지 파일만 사용할 수 있습니다."
        );

    }


    // 프론트에서도 10MB를 미리 검사
    if (
        file.size >
        10 * 1024 * 1024
    ) {

        throw new Error(
            "이미지는 10MB 이하만 업로드할 수 있습니다."
        );

    }


    const formData =
        new FormData();


    formData.append(
        "file",
        file
    );


    imageUploading = true;


    try {

        const response =
            await fetch(
                `${API_URL}/upload-image`,
                {

                    method: "POST",

                    headers:
                        getAuthHeaders(),

                    body:
                        formData

                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.detail ||
                "이미지 업로드에 실패했습니다."
            );

        }


        if (!data.image_url) {

            throw new Error(
                "서버에서 이미지 주소를 받지 못했습니다."
            );

        }


        return data.image_url;


    } finally {

        imageUploading = false;

    }

}


// ============================================================
// 기사 저장
// ============================================================

async function saveArticle() {

    if (!currentUser) {

        alert(
            "로그인이 필요합니다."
        );

        showLogin();

        return;

    }


    if (imageUploading) {

        alert(
            "이미지 업로드가 끝날 때까지 기다려주세요."
        );

        return;

    }


    const title =
        titleInput.value.trim();

    const subtitle =
        subtitleInput.value.trim();

    const author =
        authorInput.value.trim();

    const date =
        dateInput.value;

    const content =
        contentInput.value;

    const image =
        imageData;


    if (!title) {

        alert(
            "기사 제목을 입력하세요."
        );

        titleInput.focus();

        return;

    }


    const articleData = {

        title:
            title,

        subtitle:
            subtitle,

        author:
            author,

        date:
            date,

        content:
            content,

        image:
            image

    };


    try {

        let response;


        if (editingId !== null) {

            response =
                await fetch(
                    `${API_URL}/articles/${editingId}`,
                    {

                        method: "PUT",

                        headers: {

                            "Content-Type":
                                "application/json",

                            ...getAuthHeaders()

                        },

                        body:
                            JSON.stringify(
                                articleData
                            )

                    }
                );

        } else {

            response =
                await fetch(
                    `${API_URL}/articles`,
                    {

                        method: "POST",

                        headers: {

                            "Content-Type":
                                "application/json",

                            ...getAuthHeaders()

                        },

                        body:
                            JSON.stringify(
                                articleData
                            )

                    }
                );

        }


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.detail ||
                "기사 저장에 실패했습니다."
            );

        }


        if (editingId !== null) {

            alert(
                "기사가 수정되었습니다."
            );

        } else {

            alert(
                "기사가 저장되었습니다."
            );

        }


        editingId = null;


        editorTitle.textContent =
            "기사 작성";


        clearEditor();


        await loadArticles();


    } catch (error) {

        console.error(error);

        alert(
            error.message
        );

    }

}


// ============================================================
// 기사 전체 불러오기
// ============================================================

async function loadArticles() {

    try {

        const response =
            await fetch(
                `${API_URL}/articles`
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.detail ||
                "기사를 불러오지 못했습니다."
            );

        }


        articles = data;


        renderArticles(
            articles
        );


    } catch (error) {

        console.error(error);

        articleList.innerHTML = `

            <div class="empty">

                기사를 불러오지 못했습니다.

                <br>

                백엔드 서버가 실행 중인지 확인하세요.

            </div>

        `;

    }

}


// ============================================================
// 기사 목록 렌더링
// ============================================================

function renderArticles(
    articleArray
) {

    articleList.innerHTML = "";


    if (
        !articleArray ||
        articleArray.length === 0
    ) {

        articleList.innerHTML = `

            <div class="empty">

                등록된 기사가 없습니다.

            </div>

        `;

        return;

    }


    articleArray.forEach(
        article => {

            const card =
                document.createElement(
                    "div"
                );


            card.className =
                "article-card";


            card.innerHTML = `

                <div class="article-info">

                    <h3>
                        ${escapeHTML(
                            article.title
                        )}
                    </h3>

                    <p>
                        ${escapeHTML(
                            article.subtitle ||
                            ""
                        )}
                    </p>

                    <small>
                        ${escapeHTML(
                            article.author ||
                            "기자"
                        )}
                        ·
                        ${escapeHTML(
                            article.date ||
                            ""
                        )}
                        ·
                        ${escapeHTML(
                            article.owner_nickname ||
                            ""
                        )}
                    </small>

                </div>

            `;


            card.addEventListener(
                "click",
                () => {

                    viewArticle(
                        article.id
                    );

                }
            );


            articleList.appendChild(
                card
            );

        }
    );

}


// ============================================================
// 기사 검색
// ============================================================

function searchArticles() {

    const keyword =
        searchInput.value
            .trim()
            .toLowerCase();


    if (!keyword) {

        renderArticles(
            articles
        );

        return;

    }


    const filtered =
        articles.filter(
            article => {

                return (

                    (article.title || "")
                        .toLowerCase()
                        .includes(keyword)

                    ||

                    (article.subtitle || "")
                        .toLowerCase()
                        .includes(keyword)

                    ||

                    (article.author || "")
                        .toLowerCase()
                        .includes(keyword)

                    ||

                    (article.content || "")
                        .toLowerCase()
                        .includes(keyword)

                    ||

                    (article.owner_nickname || "")
                        .toLowerCase()
                        .includes(keyword)

                );

            }
        );


    renderArticles(
        filtered
    );

}


// ============================================================
// 기사 상세 보기
// ============================================================

async function viewArticle(
    articleId
) {

    try {

        const response =
            await fetch(
                `${API_URL}/articles/${articleId}`
            );


        const article =
            await response.json();


        if (!response.ok) {

            throw new Error(
                article.detail ||
                "기사를 불러오지 못했습니다."
            );

        }


        currentArticleId =
            article.id;


        hideAllPages();

        viewPage.hidden = false;


        viewTitle.textContent =
            article.title || "";


        viewSubtitle.textContent =
            article.subtitle || "";


        viewAuthor.textContent =
            article.author
                ? `${article.author} 기자`
                : "";


        viewDate.textContent =
            article.date || "";


        viewContent.textContent =
            article.content || "";


        if (article.image) {

            viewImage.src =
                getImageUrl(
                    article.image
                );

            viewImage.hidden = false;

        } else {

            viewImage.src = "";

            viewImage.hidden = true;

        }


        updateEditButton(
            article
        );


    } catch (error) {

        console.error(error);

        alert(
            error.message
        );

    }

}


// ============================================================
// 편집 버튼 상태
// ============================================================

function updateEditButton(
    article
) {

    const editButton =
        document.querySelector(
            ".edit-button"
        );


    if (!editButton) {

        return;

    }


    if (!currentUser) {

        editButton.hidden = true;

        return;

    }


    const canEdit =
        article.owner_id === currentUser.id
        ||
        Number(currentUser.is_admin) === 1;


    editButton.hidden =
        !canEdit;

}


// ============================================================
// 현재 기사 편집
// ============================================================

async function editCurrentArticle() {

    if (
        currentArticleId === null
    ) {

        return;

    }


    if (!currentUser) {

        alert(
            "로그인이 필요합니다."
        );

        showLogin();

        return;

    }


    try {

        const response =
            await fetch(
                `${API_URL}/articles/${currentArticleId}`
            );


        const article =
            await response.json();


        if (!response.ok) {

            throw new Error(
                article.detail ||
                "기사를 불러오지 못했습니다."
            );

        }


        const canEdit =
            article.owner_id === currentUser.id
            ||
            Number(currentUser.is_admin) === 1;


        if (!canEdit) {

            alert(
                "본인의 기사만 편집할 수 있습니다."
            );

            return;

        }


        editingId =
            article.id;


        titleInput.value =
            article.title || "";

        subtitleInput.value =
            article.subtitle || "";

        authorInput.value =
            article.author || "";

        dateInput.value =
            article.date || "";

        contentInput.value =
            article.content || "";


        imageData =
            article.image || "";


        if (imageData) {

            previewImage.src =
                getImageUrl(
                    imageData
                );

            previewImage.hidden =
                false;

        } else {

            previewImage.src = "";

            previewImage.hidden =
                true;

        }


        // 기존 파일 선택값은 비움
        // 기존 서버 이미지는 imageData로 유지
        imageInput.value = "";


        editorTitle.textContent =
            "기사 편집";


        hideAllPages();

        editorPage.hidden = false;


        updatePreview();


    } catch (error) {

        console.error(error);

        alert(
            error.message
        );

    }

}


// ============================================================
// 기사 삭제
// ============================================================

async function deleteArticle(
    articleId
) {

    if (!currentUser) {

        alert(
            "로그인이 필요합니다."
        );

        return;

    }


    const confirmed =
        confirm(
            "정말 이 기사를 삭제하시겠습니까?"
        );


    if (!confirmed) {

        return;

    }


    try {

        const response =
            await fetch(
                `${API_URL}/articles/${articleId}`,
                {

                    method: "DELETE",

                    headers:
                        getAuthHeaders()

                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.detail ||
                "기사 삭제에 실패했습니다."
            );

        }


        alert(
            "기사가 삭제되었습니다."
        );


        currentArticleId =
            null;


        await showArticles();


    } catch (error) {

        console.error(error);

        alert(
            error.message
        );

    }

}


// ============================================================
// 새 기사
// ============================================================

function clearEditor() {

    editingId = null;


    editorTitle.textContent =
        "기사 작성";


    titleInput.value = "";

    subtitleInput.value = "";

    authorInput.value = "";

    contentInput.value = "";


    imageInput.value = "";


    imageData = "";

    imageUploading = false;


    previewImage.src = "";

    previewImage.hidden = true;


    setToday();

    updatePreview();

}


// ============================================================
// 미리보기
// ============================================================

function updatePreview() {

    previewTitle.textContent =
        titleInput.value ||
        "기사 제목";


    previewSubtitle.textContent =
        subtitleInput.value ||
        "기사 부제가 여기에 표시됩니다.";


    previewAuthor.textContent =
        authorInput.value
            ? `${authorInput.value} 기자`
            : "홍길동 기자";


    previewDate.textContent =
        dateInput.value ||
        "";


    previewContent.textContent =
        contentInput.value ||
        "기사 본문이 여기에 표시됩니다.";


    if (imageData) {

        previewImage.src =
            getImageUrl(
                imageData
            );

        previewImage.hidden =
            false;

    } else {

        previewImage.src = "";

        previewImage.hidden =
            true;

    }

}


// ============================================================
// 이미지 업로드
// ============================================================

imageInput.addEventListener(
    "change",
    async function () {

        const file =
            this.files[0];


        if (!file) {

            return;

        }


        try {

            imageUploading = true;


            // 업로드 전 미리보기
            const localPreview =
                URL.createObjectURL(
                    file
                );


            previewImage.src =
                localPreview;

            previewImage.hidden =
                false;


            // 서버 업로드
            const uploadedImage =
                await uploadImage(
                    file
                );


            imageData =
                uploadedImage;


            // 서버 주소로 다시 설정
            previewImage.src =
                getImageUrl(
                    imageData
                );


            alert(
                "이미지가 업로드되었습니다."
            );


        } catch (error) {

            console.error(error);

            alert(
                error.message
            );


            imageData = "";

            this.value = "";

            previewImage.src = "";

            previewImage.hidden = true;


        } finally {

            imageUploading = false;

        }

    }
);


// ============================================================
// 실시간 미리보기
// ============================================================

titleInput.addEventListener(
    "input",
    updatePreview
);

subtitleInput.addEventListener(
    "input",
    updatePreview
);

authorInput.addEventListener(
    "input",
    updatePreview
);

dateInput.addEventListener(
    "input",
    updatePreview
);

contentInput.addEventListener(
    "input",
    updatePreview
);


// ============================================================
// 오늘 날짜
// ============================================================

function setToday() {

    if (dateInput.value) {

        return;

    }


    const now =
        new Date();


    const year =
        now.getFullYear();


    const month =
        String(
            now.getMonth() + 1
        ).padStart(
            2,
            "0"
        );


    const day =
        String(
            now.getDate()
        ).padStart(
            2,
            "0"
        );


    dateInput.value =
        `${year}-${month}-${day}`;


    previewDate.textContent =
        dateInput.value;

}


// ============================================================
// HTML 이스케이프
// ============================================================

function escapeHTML(
    value
) {

    if (
        value === null ||
        value === undefined
    ) {

        return "";

    }


    return String(value)
        .replace(
            /&/g,
            "&amp;"
        )
        .replace(
            /</g,
            "&lt;"
        )
        .replace(
            />/g,
            "&gt;"
        )
        .replace(
            /"/g,
            "&quot;"
        )
        .replace(
            /'/g,
            "&#039;"
        );

}


// ============================================================
// 시작
// ============================================================

loadCurrentUser();

setToday();

updatePreview();