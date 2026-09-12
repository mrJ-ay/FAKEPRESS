
// =========================================================
// FAKEPRESS
// =========================================================

// 로컬에서는 기존 백엔드 사용
// Render에서는 같은 서버의 API 사용
const API_URL =
    window.location.hostname === "127.0.0.1" ||
    window.location.hostname === "localhost"
        ? "http://127.0.0.1:8000"
        : window.location.origin;


// =========================================================
// GLOBAL STATE
// =========================================================

let currentUser =
    JSON.parse(localStorage.getItem("fakepress_user")) || null;

let token =
    localStorage.getItem("fakepress_token") || null;

let articles = [];

let currentArticle = null;
let editingArticleId = null;
let imageData = "";


// =========================================================
// ELEMENTS
// =========================================================

const loginPage = document.getElementById("loginPage");
const editorPage = document.getElementById("editorPage");
const articlesPage = document.getElementById("articlesPage");
const viewPage = document.getElementById("viewPage");

const adminButton = document.getElementById("adminButton");
const loginButton = document.getElementById("loginButton");

const userInfo = document.getElementById("userInfo");
const loggedInUser = document.getElementById("loggedInUser");

const articleList = document.getElementById("articleList");


// =========================================================
// INITIALIZE
// =========================================================

document.addEventListener("DOMContentLoaded", () => {
    updateUI();
    loadArticles();

    const imageInput = document.getElementById("image");

    if (imageInput) {
        imageInput.addEventListener(
            "change",
            handleImageUpload
        );
    }
});


// =========================================================
// AUTH UI
// =========================================================

function updateUI() {
    if (currentUser) {
        loginButton.textContent = "로그아웃";
        loginButton.onclick = logout;

        userInfo.hidden = false;

        if (loggedInUser) {
            loggedInUser.textContent =
                `${currentUser.nickname}님`;
        }

        if (
            adminButton &&
            Number(currentUser.is_admin) === 1
        ) {
            adminButton.style.display = "inline-block";
        } else if (adminButton) {
            adminButton.style.display = "none";
        }

    } else {
        loginButton.textContent = "로그인";
        loginButton.onclick = showLogin;

        userInfo.hidden = true;

        if (adminButton) {
            adminButton.style.display = "none";
        }
    }
}


// =========================================================
// PAGE NAVIGATION
// =========================================================

function hideAllPages() {
    if (loginPage) loginPage.hidden = true;
    if (editorPage) editorPage.hidden = true;
    if (articlesPage) articlesPage.hidden = true;
    if (viewPage) viewPage.hidden = true;
}

function showLogin() {
    hideAllPages();

    if (loginPage) {
        loginPage.hidden = false;
    }
}

function showEditor() {
    if (!currentUser) {
        alert("로그인이 필요합니다.");
        showLogin();
        return;
    }

    hideAllPages();

    if (editorPage) {
        editorPage.hidden = false;
    }
}

function showArticles() {
    hideAllPages();

    if (articlesPage) {
        articlesPage.hidden = false;
    }

    loadArticles();
}


// =========================================================
// LOGIN
// =========================================================

async function login() {
    const nickname =
        document.getElementById("loginNickname").value.trim();

    const password =
        document.getElementById("loginPassword").value;

    if (!nickname || !password) {
        alert("닉네임과 비밀번호를 입력하세요.");
        return;
    }

    try {
        const response = await fetch(
            `${API_URL}/login`,
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    nickname,
                    password
                })
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail || "로그인에 실패했습니다."
            );
        }

        token = data.access_token;
        currentUser = data.user;

        localStorage.setItem(
            "fakepress_token",
            token
        );

        localStorage.setItem(
            "fakepress_user",
            JSON.stringify(currentUser)
        );

        updateUI();

        alert("로그인되었습니다.");

        showArticles();

    } catch (error) {
        console.error(error);
        alert(error.message);
    }
}


// =========================================================
// REGISTER
// =========================================================

async function registerUser() {
    const nickname =
        document.getElementById("loginNickname").value.trim();

    const password =
        document.getElementById("loginPassword").value;

    if (!nickname || !password) {
        alert("닉네임과 비밀번호를 입력하세요.");
        return;
    }

    try {
        const response = await fetch(
            `${API_URL}/register`,
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    nickname,
                    password
                })
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail || "회원가입에 실패했습니다."
            );
        }

        alert(data.message);

    } catch (error) {
        console.error(error);
        alert(error.message);
    }
}


// =========================================================
// LOGOUT
// =========================================================

function logout() {
    currentUser = null;
    token = null;

    localStorage.removeItem(
        "fakepress_token"
    );

    localStorage.removeItem(
        "fakepress_user"
    );

    updateUI();

    alert("로그아웃되었습니다.");

    showArticles();
}


// =========================================================
// AUTH HEADER
// =========================================================

function authHeaders() {
    return token
        ? {
            Authorization: `Bearer ${token}`
        }
        : {};
}


// =========================================================
// IMAGE URL
// =========================================================

function getImageUrl(image) {
    if (!image) {
        return "";
    }

    // 기존 Base64 이미지
    if (image.startsWith("data:")) {
        return image;
    }

    // 이미 완전한 URL
    if (
        image.startsWith("http://") ||
        image.startsWith("https://")
    ) {
        return image;
    }

    // /uploads/... 같은 서버 상대경로
    return `${API_URL}${
        image.startsWith("/")
            ? ""
            : "/"
    }${image}`;
}


// =========================================================
// IMAGE UPLOAD
// =========================================================

async function handleImageUpload(event) {
    const file = event.target.files[0];

    if (!file) {
        return;
    }

    if (!currentUser || !token) {
        alert("로그인이 필요합니다.");

        event.target.value = "";
        return;
    }

    // 먼저 로컬 미리보기
    const localUrl =
        URL.createObjectURL(file);

    const previewImage =
        document.getElementById("previewImage");

    if (previewImage) {
        previewImage.src = localUrl;
        previewImage.hidden = false;
    }

    try {
        const uploadedUrl =
            await uploadImage(file);

        imageData = uploadedUrl;

        if (previewImage) {
            previewImage.src =
                getImageUrl(imageData);
        }

    } catch (error) {
        console.error(error);

        alert(error.message);

        event.target.value = "";
        imageData = "";

        if (previewImage) {
            previewImage.src = "";
            previewImage.hidden = true;
        }
    }
}


async function uploadImage(file) {
    const allowedTypes = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif"
    ];

    if (!allowedTypes.includes(file.type)) {
        throw new Error(
            "JPG, PNG, WEBP, GIF 이미지만 업로드할 수 있습니다."
        );
    }

    if (file.size > 10 * 1024 * 1024) {
        throw new Error(
            "이미지는 10MB 이하만 업로드할 수 있습니다."
        );
    }

    const formData = new FormData();

    formData.append(
        "file",
        file
    );

    const response = await fetch(
        `${API_URL}/upload-image`,
        {
            method: "POST",

            headers: {
                Authorization: `Bearer ${token}`
            },

            body: formData
        }
    );

    const data = await response.json();

    if (!response.ok) {
        throw new Error(
            data.detail ||
            "이미지 업로드에 실패했습니다."
        );
    }

    return data.image_url;
}


// =========================================================
// SAVE ARTICLE
// =========================================================

async function saveArticle() {
    if (!currentUser || !token) {
        alert("로그인이 필요합니다.");
        showLogin();
        return;
    }

    const title =
        document.getElementById("title").value.trim();

    const subtitle =
        document.getElementById("subtitle").value;

    const author =
        document.getElementById("author").value;

    const date =
        document.getElementById("date").value;

    const content =
        document.getElementById("content").value;

    if (!title) {
        alert("기사 제목을 입력하세요.");
        return;
    }

    const articleData = {
        title,
        subtitle,
        author,
        date,
        content,
        image: imageData || ""
    };

    try {
        let response;

        if (editingArticleId) {
            response = await fetch(
                `${API_URL}/articles/${editingArticleId}`,
                {
                    method: "PUT",

                    headers: {
                        "Content-Type": "application/json",
                        ...authHeaders()
                    },

                    body: JSON.stringify(articleData)
                }
            );

        } else {
            response = await fetch(
                `${API_URL}/articles`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type": "application/json",
                        ...authHeaders()
                    },

                    body: JSON.stringify(articleData)
                }
            );
        }

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail ||
                "기사 저장에 실패했습니다."
            );
        }

        alert(
            editingArticleId
                ? "기사가 수정되었습니다."
                : "기사가 저장되었습니다."
        );

        editingArticleId = null;

        clearEditor();
        await loadArticles();
        showArticles();

    } catch (error) {
        console.error(error);
        alert(error.message);
    }
}


// =========================================================
// LOAD ARTICLES
// =========================================================

async function loadArticles() {
    try {
        const response = await fetch(
            `${API_URL}/articles`
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail ||
                "기사 목록을 불러오지 못했습니다."
            );
        }

        articles = data;

        renderArticles(articles);

    } catch (error) {
        console.error(error);
    }
}


// =========================================================
// RENDER ARTICLE LIST
// =========================================================

function renderArticles(list) {
    if (!articleList) {
        return;
    }

    articleList.innerHTML = "";

    if (!list.length) {
        articleList.innerHTML =
            "<p>등록된 기사가 없습니다.</p>";

        return;
    }

    list.forEach(article => {
        const card =
            document.createElement("div");

        card.className = "article-card";

        card.innerHTML = `
            ${
                article.image
                    ? `
                        <img
                            src="${getImageUrl(article.image)}"
                            class="news-image"
                        >
                    `
                    : ""
            }

            <h2>${escapeHtml(article.title)}</h2>

            <h3>
                ${escapeHtml(article.subtitle || "")}
            </h3>

            <p>
                ${escapeHtml(article.author || "")}
                ${article.author ? " 기자" : ""}
            </p>

            <p>
                ${escapeHtml(article.date || "")}
            </p>

            <button
                onclick="viewArticle(${article.id})"
            >
                기사 보기
            </button>
        `;

        articleList.appendChild(card);
    });
}


// =========================================================
// SEARCH
// =========================================================

function searchArticles() {
    const keyword =
        document.getElementById("search")
            .value
            .trim()
            .toLowerCase();

    if (!keyword) {
        renderArticles(articles);
        return;
    }

    const filtered =
        articles.filter(article => {
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
            );
        });

    renderArticles(filtered);
}


// =========================================================
// VIEW ARTICLE
// =========================================================

async function viewArticle(id) {
    try {
        const response = await fetch(
            `${API_URL}/articles/${id}`
        );

        const article =
            await response.json();

        if (!response.ok) {
            throw new Error(
                article.detail ||
                "기사를 불러오지 못했습니다."
            );
        }

        currentArticle = article;

        hideAllPages();

        if (viewPage) {
            viewPage.hidden = false;
        }

        document.getElementById(
            "viewTitle"
        ).textContent =
            article.title || "";

        document.getElementById(
            "viewSubtitle"
        ).textContent =
            article.subtitle || "";

        document.getElementById(
            "viewAuthor"
        ).textContent =
            article.author
                ? `${article.author} 기자`
                : "";

        document.getElementById(
            "viewDate"
        ).textContent =
            article.date || "";

        document.getElementById(
            "viewContent"
        ).textContent =
            article.content || "";

        const viewImage =
            document.getElementById(
                "viewImage"
            );

        if (article.image) {
            viewImage.src =
                getImageUrl(article.image);

            viewImage.hidden = false;
        } else {
            viewImage.src = "";
            viewImage.hidden = true;
        }

    } catch (error) {
        console.error(error);
        alert(error.message);
    }
}


// =========================================================
// EDIT ARTICLE
// =========================================================

function editCurrentArticle() {
    if (!currentArticle) {
        return;
    }

    if (!currentUser) {
        alert("로그인이 필요합니다.");
        return;
    }

    const canEdit =
        Number(currentArticle.owner_id) ===
            Number(currentUser.id)
        ||
        Number(currentUser.is_admin) === 1;

    if (!canEdit) {
        alert("본인의 기사만 수정할 수 있습니다.");
        return;
    }

    editingArticleId =
        currentArticle.id;

    hideAllPages();

    editorPage.hidden = false;

    document.getElementById("editorTitle")
        .textContent = "기사 편집";

    document.getElementById("title")
        .value =
        currentArticle.title || "";

    document.getElementById("subtitle")
        .value =
        currentArticle.subtitle || "";

    document.getElementById("author")
        .value =
        currentArticle.author || "";

    document.getElementById("date")
        .value =
        currentArticle.date || "";

    document.getElementById("content")
        .value =
        currentArticle.content || "";

    imageData =
        currentArticle.image || "";

    const previewImage =
        document.getElementById(
            "previewImage"
        );

    if (imageData) {
        previewImage.src =
            getImageUrl(imageData);

        previewImage.hidden = false;
    } else {
        previewImage.src = "";
        previewImage.hidden = true;
    }

    const imageInput =
        document.getElementById("image");

    if (imageInput) {
        imageInput.value = "";
    }

    updatePreview();
}


// =========================================================
// DELETE ARTICLE
// =========================================================

async function deleteArticle(id) {
    if (!currentUser || !token) {
        alert("로그인이 필요합니다.");
        return;
    }

    const article =
        articles.find(
            item => Number(item.id) === Number(id)
        );

    if (!article) {
        return;
    }

    const canDelete =
        Number(article.owner_id) ===
            Number(currentUser.id)
        ||
        Number(currentUser.is_admin) === 1;

    if (!canDelete) {
        alert("본인의 기사만 삭제할 수 있습니다.");
        return;
    }

    if (
        !confirm(
            "정말 이 기사를 삭제하시겠습니까?"
        )
    ) {
        return;
    }

    try {
        const response = await fetch(
            `${API_URL}/articles/${id}`,
            {
                method: "DELETE",
                headers: authHeaders()
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

        alert(data.message);

        await loadArticles();
        showArticles();

    } catch (error) {
        console.error(error);
        alert(error.message);
    }
}


// =========================================================
// CLEAR EDITOR
// =========================================================

function clearEditor() {
    editingArticleId = null;
    imageData = "";

    document.getElementById("editorTitle")
        .textContent = "기사 작성";

    document.getElementById("title")
        .value = "";

    document.getElementById("subtitle")
        .value = "";

    document.getElementById("author")
        .value = "";

    document.getElementById("date")
        .value = "";

    document.getElementById("content")
        .value = "";

    const imageInput =
        document.getElementById("image");

    if (imageInput) {
        imageInput.value = "";
    }

    const previewImage =
        document.getElementById(
            "previewImage"
        );

    if (previewImage) {
        previewImage.src = "";
        previewImage.hidden = true;
    }

    updatePreview();
}


// =========================================================
// PREVIEW
// =========================================================

function updatePreview() {
    const title =
        document.getElementById("title")
            .value;

    const subtitle =
        document.getElementById("subtitle")
            .value;

    const author =
        document.getElementById("author")
            .value;

    const date =
        document.getElementById("date")
            .value;

    const content =
        document.getElementById("content")
            .value;

    document.getElementById(
        "previewTitle"
    ).textContent =
        title || "기사 제목";

    document.getElementById(
        "previewSubtitle"
    ).textContent =
        subtitle ||
        "기사 부제가 여기에 표시됩니다.";

    document.getElementById(
        "previewAuthor"
    ).textContent =
        author
            ? `${author} 기자`
            : "홍길동 기자";

    document.getElementById(
        "previewDate"
    ).textContent =
        date || "";

    document.getElementById(
        "previewContent"
    ).textContent =
        content ||
        "기사 본문이 여기에 표시됩니다.";
}


// =========================================================
// LIVE PREVIEW
// =========================================================

[
    "title",
    "subtitle",
    "author",
    "date",
    "content"
].forEach(id => {
    const element =
        document.getElementById(id);

    if (element) {
        element.addEventListener(
            "input",
            updatePreview
        );
    }

    if (element) {
        element.addEventListener(
            "change",
            updatePreview
        );
    }
});


// =========================================================
// ESCAPE HTML
// =========================================================

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

