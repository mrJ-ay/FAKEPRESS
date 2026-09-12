// =========================================================
// FAKEPRESS - script.js
// =========================================================

const API_URL = "https://fakepress.onrender.com";
const TOKEN_KEY = "fakepress_token";

let allArticles = [];
let currentArticleId = null;
let editingArticle = null;


// =========================================================
// TOKEN
// =========================================================

function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

function setToken(token) {
    localStorage.setItem(TOKEN_KEY, token);
}

function removeToken() {
    localStorage.removeItem(TOKEN_KEY);
}


// =========================================================
// RESPONSE
// =========================================================

async function parseResponse(response) {
    let data = null;

    try {
        data = await response.json();
    } catch {
        data = null;
    }

    if (!response.ok) {
        const message =
            data?.detail ||
            data?.message ||
            "서버 요청에 실패했습니다.";

        throw new Error(message);
    }

    return data;
}


// =========================================================
// PAGE NAVIGATION
// =========================================================

function showPage(pageId) {
    const pages = [
        "loginPage",
        "editorPage",
        "articlesPage",
        "viewPage"
    ];

    pages.forEach(id => {
        const page = document.getElementById(id);

        if (page) {
            page.hidden = id !== pageId;
        }
    });
}


// =========================================================
// LOGIN PAGE
// =========================================================

function showLogin() {
    showPage("loginPage");
}


// =========================================================
// EDITOR PAGE
// =========================================================

function showEditor() {
    if (!getToken()) {
        alert("로그인이 필요합니다.");
        showLogin();
        return;
    }

    showPage("editorPage");

    const editorTitle =
        document.getElementById("editorTitle");

    if (editingArticle) {
        if (editorTitle) {
            editorTitle.textContent = "기사 편집";
        }
    } else {
        if (editorTitle) {
            editorTitle.textContent = "기사 작성";
        }
    }

    updatePreview();
}


// =========================================================
// ARTICLES PAGE
// =========================================================

async function showArticles() {
    showPage("articlesPage");

    await loadArticlesForPage();
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
            `${API_URL}/auth/register`,
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

        const data = await parseResponse(response);

        alert(
            data?.message ||
            "회원가입이 완료되었습니다."
        );

    } catch (error) {
        console.error(error);
        alert(error.message);
    }
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
            `${API_URL}/auth/login`,
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

        const data = await parseResponse(response);

        const token =
            data?.access_token ||
            data?.token;

        if (!token) {
            throw new Error(
                "로그인 토큰을 받지 못했습니다."
            );
        }

        setToken(token);

        alert("로그인되었습니다.");

        await checkLogin();

        showEditor();

    } catch (error) {
        console.error(error);
        alert(error.message);
    }
}


// =========================================================
// LOGOUT
// =========================================================

function logout() {
    removeToken();

    currentArticleId = null;
    editingArticle = null;

    const userInfo =
        document.getElementById("userInfo");

    const loginButton =
        document.getElementById("loginButton");

    const adminButton =
        document.getElementById("adminButton");

    if (userInfo) {
        userInfo.hidden = true;
    }

    if (loginButton) {
        loginButton.style.display = "";
    }

    if (adminButton) {
        adminButton.style.display = "none";
    }

    alert("로그아웃되었습니다.");

    showLogin();
}


// =========================================================
// CURRENT USER
// =========================================================

async function getCurrentUser() {
    const token = getToken();

    if (!token) {
        return null;
    }

    const response = await fetch(
        `${API_URL}/auth/me`,
        {
            method: "GET",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        }
    );

    if (response.status === 401) {
        removeToken();
        return null;
    }

    return await parseResponse(response);
}


// =========================================================
// CHECK LOGIN
// =========================================================

async function checkLogin() {
    const loginButton =
        document.getElementById("loginButton");

    const userInfo =
        document.getElementById("userInfo");

    const loggedInUser =
        document.getElementById("loggedInUser");

    const adminButton =
        document.getElementById("adminButton");

    if (!getToken()) {
        if (loginButton) {
            loginButton.style.display = "";
        }

        if (userInfo) {
            userInfo.hidden = true;
        }

        if (adminButton) {
            adminButton.style.display = "none";
        }

        return null;
    }

    try {
        const user = await getCurrentUser();

        if (!user) {
            if (loginButton) {
                loginButton.style.display = "";
            }

            if (userInfo) {
                userInfo.hidden = true;
            }

            if (adminButton) {
                adminButton.style.display = "none";
            }

            return null;
        }

        if (loginButton) {
            loginButton.style.display = "none";
        }

        if (userInfo) {
            userInfo.hidden = false;
        }

        if (loggedInUser) {
            loggedInUser.textContent =
                `${user.nickname || user.username || "사용자"}님`;
        }

        if (adminButton) {
            const isAdmin =
                user.is_admin === 1 ||
                user.is_admin === true;

            adminButton.style.display =
                isAdmin ? "" : "none";
        }

        return user;

    } catch (error) {
        console.error(error);

        removeToken();

        if (loginButton) {
            loginButton.style.display = "";
        }

        if (userInfo) {
            userInfo.hidden = true;
        }

        if (adminButton) {
            adminButton.style.display = "none";
        }

        return null;
    }
}


// =========================================================
// IMAGE UPLOAD
// =========================================================

async function uploadImage(file) {
    if (!file) {
        return null;
    }

    const token = getToken();

    if (!token) {
        throw new Error("로그인이 필요합니다.");
    }

    const formData = new FormData();

    formData.append("file", file);

    const response = await fetch(
        `${API_URL}/upload-image`,
        {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`
            },
            body: formData
        }
    );

    const data = await parseResponse(response);

    return (
        data?.url ||
        data?.image_url ||
        data?.filename ||
        data?.path ||
        null
    );
}


// =========================================================
// IMAGE URL
// =========================================================

function getImageUrl(image) {
    if (!image) {
        return "";
    }

    const value = String(image).trim();

    if (!value) {
        return "";
    }

    // 완전한 URL
    if (
        value.startsWith("http://") ||
        value.startsWith("https://") ||
        value.startsWith("data:")
    ) {
        return value;
    }

    // /uploads/xxx.jpg
    if (value.startsWith("/")) {
        return `${API_URL}${value}`;
    }

    // uploads/xxx.jpg
    return `${API_URL}/${value}`;
}


// =========================================================
// CREATE ARTICLE
// =========================================================

async function createArticle(articleData) {
    const token = getToken();

    if (!token) {
        throw new Error("로그인이 필요합니다.");
    }

    const response = await fetch(
        `${API_URL}/articles`,
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify(articleData)
        }
    );

    return await parseResponse(response);
}


// =========================================================
// GET ARTICLES
// =========================================================

async function getArticles() {
    const response = await fetch(
        `${API_URL}/articles`,
        {
            method: "GET"
        }
    );

    return await parseResponse(response);
}


// =========================================================
// GET ONE ARTICLE
// =========================================================

async function getArticle(articleId) {
    const response = await fetch(
        `${API_URL}/articles/${articleId}`,
        {
            method: "GET"
        }
    );

    return await parseResponse(response);
}


// =========================================================
// UPDATE ARTICLE
// =========================================================

async function updateArticle(articleId, articleData) {
    const token = getToken();

    if (!token) {
        throw new Error("로그인이 필요합니다.");
    }

    const response = await fetch(
        `${API_URL}/articles/${articleId}`,
        {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify(articleData)
        }
    );

    return await parseResponse(response);
}


// =========================================================
// DELETE ARTICLE
// =========================================================

async function deleteArticle(articleId) {
    const token = getToken();

    if (!token) {
        throw new Error("로그인이 필요합니다.");
    }

    const response = await fetch(
        `${API_URL}/articles/${articleId}`,
        {
            method: "DELETE",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        }
    );

    return await parseResponse(response);
}


// =========================================================
// SAVE ARTICLE
// =========================================================

async function saveArticle() {
    if (!getToken()) {
        alert("로그인이 필요합니다.");
        showLogin();
        return;
    }

    const title =
        document.getElementById("title").value.trim();

    const subtitle =
        document.getElementById("subtitle").value.trim();

    const author =
        document.getElementById("author").value.trim();

    const date =
        document.getElementById("date").value;

    const content =
        document.getElementById("content").value.trim();

    const imageInput =
        document.getElementById("image");

    if (!title) {
        alert("기사 제목을 입력하세요.");
        return;
    }

    if (!author) {
        alert("기자명을 입력하세요.");
        return;
    }

    if (!content) {
        alert("기사 본문을 입력하세요.");
        return;
    }

    try {
        let imageUrl =
            editingArticle?.image_url ||
            editingArticle?.image ||
            null;

        // 새 이미지가 선택된 경우 업로드
        if (
            imageInput &&
            imageInput.files &&
            imageInput.files.length > 0
        ) {
            imageUrl =
                await uploadImage(imageInput.files[0]);
        }

        const articleData = {
            title,
            subtitle,
            author,
            date,
            content
        };

        // 중요:
        // 백엔드 ArticleRequest는 image_url이 아니라 image를 사용함
        if (imageUrl) {
            articleData.image = imageUrl;
        }

        let result;

        if (editingArticle && currentArticleId) {

            result = await updateArticle(
                currentArticleId,
                articleData
            );

            alert("기사가 수정되었습니다.");

        } else {

            result = await createArticle(
                articleData
            );

            alert("기사가 저장되었습니다.");
        }

        console.log("기사 저장 결과:", result);

        editingArticle = null;
        currentArticleId = null;

        clearEditor(false);

        showArticles();

    } catch (error) {
        console.error(error);
        alert(error.message);
    }
}


// =========================================================
// CLEAR EDITOR
// =========================================================

function clearEditor(showPageAfter = true) {
    const title =
        document.getElementById("title");

    const subtitle =
        document.getElementById("subtitle");

    const author =
        document.getElementById("author");

    const date =
        document.getElementById("date");

    const image =
        document.getElementById("image");

    const content =
        document.getElementById("content");

    if (title) title.value = "";
    if (subtitle) subtitle.value = "";
    if (author) author.value = "";
    if (content) content.value = "";

    if (date) {
        const today =
            new Date().toISOString().split("T")[0];

        date.value = today;
    }

    if (image) {
        image.value = "";
    }

    editingArticle = null;
    currentArticleId = null;

    const editorTitle =
        document.getElementById("editorTitle");

    if (editorTitle) {
        editorTitle.textContent = "기사 작성";
    }

    updatePreview();

    if (showPageAfter) {
        showEditor();
    }
}


// =========================================================
// LOAD ARTICLES
// =========================================================

async function loadArticlesForPage() {
    const list =
        document.getElementById("articleList");

    if (!list) {
        return;
    }

    list.innerHTML =
        "<p>기사를 불러오는 중...</p>";

    try {
        const data = await getArticles();

        if (Array.isArray(data)) {
            allArticles = data;
        } else if (Array.isArray(data?.articles)) {
            allArticles = data.articles;
        } else {
            allArticles = [];
        }

        console.log("불러온 기사:", allArticles);

        renderArticles(allArticles);

    } catch (error) {
        console.error(error);

        list.innerHTML =
            `<p>기사 불러오기 실패: ${escapeHtml(error.message)}</p>`;
    }
}


// =========================================================
// RENDER ARTICLES
// =========================================================

function renderArticles(articles) {
    const list =
        document.getElementById("articleList");

    if (!list) {
        return;
    }

    if (!articles || articles.length === 0) {
        list.innerHTML =
            "<p>등록된 기사가 없습니다.";

        return;
    }

    list.innerHTML = "";

    articles.forEach(article => {

        const articleId =
            article.id ??
            article.article_id;

        const card =
            document.createElement("div");

        card.className = "article-card";

        const title =
            article.title || "제목 없음";

        const subtitle =
            article.subtitle || "";

        const author =
            article.author || "기자";

        const date =
            article.date || "";

        const rawImage =
            article.image_url ||
            article.image ||
            "";

        const image =
            getImageUrl(rawImage);

        console.log(
            "기사 이미지:",
            rawImage,
            "→",
            image
        );

        card.innerHTML = `
            ${
                image
                    ? `
                        <img
                            src="${escapeAttribute(image)}"
                            class="news-image"
                            alt=""
                            loading="lazy"
                        >
                      `
                    : ""
            }

            <h3>
                ${escapeHtml(title)}
            </h3>

            ${
                subtitle
                    ? `
                        <p>
                            ${escapeHtml(subtitle)}
                        </p>
                      `
                    : ""
            }

            <small>
                ${escapeHtml(author)}
                ${date ? " · " + escapeHtml(date) : ""}
            </small>
        `;

        card.addEventListener(
            "click",
            () => {
                if (articleId !== undefined) {
                    viewArticle(articleId);
                }
            }
        );

        list.appendChild(card);
    });
}


// =========================================================
// SEARCH
// =========================================================

function searchArticles() {
    const searchInput =
        document.getElementById("search");

    if (!searchInput) {
        return;
    }

    const keyword =
        searchInput.value.trim().toLowerCase();

    if (!keyword) {
        renderArticles(allArticles);
        return;
    }

    const filtered =
        allArticles.filter(article => {

            const title =
                String(article.title || "")
                    .toLowerCase();

            const subtitle =
                String(article.subtitle || "")
                    .toLowerCase();

            const content =
                String(article.content || "")
                    .toLowerCase();

            const author =
                String(article.author || "")
                    .toLowerCase();

            return (
                title.includes(keyword) ||
                subtitle.includes(keyword) ||
                content.includes(keyword) ||
                author.includes(keyword)
            );
        });

    renderArticles(filtered);
}


// =========================================================
// VIEW ARTICLE
// =========================================================

async function viewArticle(articleId) {
    try {
        const article =
            await getArticle(articleId);

        currentArticleId =
            article.id ??
            article.article_id ??
            articleId;

        editingArticle = article;

        const title =
            document.getElementById("viewTitle");

        const subtitle =
            document.getElementById("viewSubtitle");

        const author =
            document.getElementById("viewAuthor");

        const date =
            document.getElementById("viewDate");

        const content =
            document.getElementById("viewContent");

        const image =
            document.getElementById("viewImage");

        if (title) {
            title.textContent =
                article.title || "";
        }

        if (subtitle) {
            subtitle.textContent =
                article.subtitle || "";
        }

        if (author) {
            author.textContent =
                article.author
                    ? `${article.author} 기자`
                    : "";
        }

        if (date) {
            date.textContent =
                article.date || "";
        }

        if (content) {
            content.textContent =
                article.content || "";
        }

        const rawImageUrl =
            article.image_url ||
            article.image ||
            "";

        const imageUrl =
            getImageUrl(rawImageUrl);

        console.log(
            "기사 보기 이미지:",
            rawImageUrl,
            "→",
            imageUrl
        );

        if (image && imageUrl) {
            image.src = imageUrl;
            image.hidden = false;
        } else if (image) {
            image.src = "";
            image.hidden = true;
        }

        showPage("viewPage");

    } catch (error) {
        console.error(error);
        alert(error.message);
    }
}


// =========================================================
// EDIT CURRENT ARTICLE
// =========================================================

async function editCurrentArticle() {
    if (!currentArticleId) {
        alert("편집할 기사가 없습니다.");
        return;
    }

    if (!getToken()) {
        alert("로그인이 필요합니다.");
        showLogin();
        return;
    }

    try {
        const article =
            editingArticle ||
            await getArticle(currentArticleId);

        editingArticle = article;

        const articleId =
            article.id ??
            article.article_id ??
            currentArticleId;

        currentArticleId = articleId;

        document.getElementById("title").value =
            article.title || "";

        document.getElementById("subtitle").value =
            article.subtitle || "";

        document.getElementById("author").value =
            article.author || "";

        document.getElementById("date").value =
            article.date || "";

        document.getElementById("content").value =
            article.content || "";

        document.getElementById("image").value = "";

        const editorTitle =
            document.getElementById("editorTitle");

        if (editorTitle) {
            editorTitle.textContent =
                "기사 편집";
        }

        showPage("editorPage");

        updatePreview();

    } catch (error) {
        console.error(error);
        alert(error.message);
    }
}


// =========================================================
// PREVIEW
// =========================================================

function updatePreview() {
    const title =
        document.getElementById("title")?.value || "";

    const subtitle =
        document.getElementById("subtitle")?.value || "";

    const author =
        document.getElementById("author")?.value || "";

    const date =
        document.getElementById("date")?.value || "";

    const content =
        document.getElementById("content")?.value || "";

    const previewTitle =
        document.getElementById("previewTitle");

    const previewSubtitle =
        document.getElementById("previewSubtitle");

    const previewAuthor =
        document.getElementById("previewAuthor");

    const previewDate =
        document.getElementById("previewDate");

    const previewContent =
        document.getElementById("previewContent");

    if (previewTitle) {
        previewTitle.textContent =
            title || "기사 제목";
    }

    if (previewSubtitle) {
        previewSubtitle.textContent =
            subtitle ||
            "기사 부제가 여기에 표시됩니다.";
    }

    if (previewAuthor) {
        previewAuthor.textContent =
            author
                ? `${author} 기자`
                : "홍길동 기자";
    }

    if (previewDate) {
        previewDate.textContent =
            date || "";
    }

    if (previewContent) {
        previewContent.textContent =
            content ||
            "기사 본문이 여기에 표시됩니다.";
    }
}


// =========================================================
// IMAGE PREVIEW
// =========================================================

function updateImagePreview() {
    const input =
        document.getElementById("image");

    const preview =
        document.getElementById("previewImage");

    if (!input || !preview) {
        return;
    }

    const file =
        input.files?.[0];

    if (!file) {
        preview.src = "";
        preview.hidden = true;
        return;
    }

    const url =
        URL.createObjectURL(file);

    preview.src = url;
    preview.hidden = false;
}


// =========================================================
// ADMIN API
// =========================================================

async function getAdminUsers() {
    const token = getToken();

    const response = await fetch(
        `${API_URL}/admin/users`,
        {
            headers: {
                "Authorization": `Bearer ${token}`
            }
        }
    );

    return await parseResponse(response);
}


async function makeAdmin(userId) {
    const token = getToken();

    const response = await fetch(
        `${API_URL}/admin/make-admin/${userId}`,
        {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        }
    );

    return await parseResponse(response);
}


async function removeAdmin(userId) {
    const token = getToken();

    const response = await fetch(
        `${API_URL}/admin/remove-admin/${userId}`,
        {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        }
    );

    return await parseResponse(response);
}


async function banUser(userId) {
    const token = getToken();

    const response = await fetch(
        `${API_URL}/admin/ban/${userId}`,
        {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        }
    );

    return await parseResponse(response);
}


async function unbanUser(userId) {
    const token = getToken();

    const response = await fetch(
        `${API_URL}/admin/unban/${userId}`,
        {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        }
    );

    return await parseResponse(response);
}


async function getAdminArticles() {
    const token = getToken();

    const response = await fetch(
        `${API_URL}/admin/articles`,
        {
            headers: {
                "Authorization": `Bearer ${token}`
            }
        }
    );

    return await parseResponse(response);
}


async function adminDeleteArticle(articleId) {
    const token = getToken();

    const response = await fetch(
        `${API_URL}/admin/articles/${articleId}`,
        {
            method: "DELETE",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        }
    );

    return await parseResponse(response);
}


// =========================================================
// HTML ESCAPE
// =========================================================

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


function escapeAttribute(value) {
    return escapeHtml(value);
}


// =========================================================
// DOM READY
// =========================================================

document.addEventListener(
    "DOMContentLoaded",
    async function () {

        // 오늘 날짜
        const date =
            document.getElementById("date");

        if (date && !date.value) {
            date.value =
                new Date()
                    .toISOString()
                    .split("T")[0];
        }

        // 미리보기 이벤트
        const previewInputs = [
            "title",
            "subtitle",
            "author",
            "date",
            "content"
        ];

        previewInputs.forEach(id => {

            const element =
                document.getElementById(id);

            if (element) {
                element.addEventListener(
                    "input",
                    updatePreview
                );

                element.addEventListener(
                    "change",
                    updatePreview
                );
            }
        });

        const imageInput =
            document.getElementById("image");

        if (imageInput) {
            imageInput.addEventListener(
                "change",
                updateImagePreview
            );
        }

        await checkLogin();

        updatePreview();
    }
);


// =========================================================
// INLINE HTML onclick 호환
// =========================================================

window.showLogin = showLogin;
window.showEditor = showEditor;
window.showArticles = showArticles;

window.login = login;
window.registerUser = registerUser;
window.logout = logout;

window.saveArticle = saveArticle;
window.clearEditor = clearEditor;

window.searchArticles = searchArticles;
window.editCurrentArticle = editCurrentArticle;

window.viewArticle = viewArticle;

window.updatePreview = updatePreview;

window.getToken = getToken;
window.setToken = setToken;
window.removeToken = removeToken;

window.getCurrentUser = getCurrentUser;
window.checkLogin = checkLogin;

window.uploadImage = uploadImage;
window.getImageUrl = getImageUrl;

window.createArticle = createArticle;
window.getArticles = getArticles;
window.getArticle = getArticle;
window.updateArticle = updateArticle;
window.deleteArticle = deleteArticle;

window.getAdminUsers = getAdminUsers;
window.makeAdmin = makeAdmin;
window.removeAdmin = removeAdmin;
window.banUser = banUser;
window.unbanUser = unbanUser;
window.getAdminArticles = getAdminArticles;
window.adminDeleteArticle = adminDeleteArticle;