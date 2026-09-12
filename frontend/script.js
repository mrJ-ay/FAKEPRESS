
// =========================================================
// FAKEPRESS SCRIPT
// =========================================================

const API_URL = "https://fakepress.onrender.com";

const TOKEN_KEY = "fakepress_token";


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
// API RESPONSE
// =========================================================

async function parseResponse(response) {
    const rawText = await response.text();

    let data = {};

    if (rawText) {
        try {
            data = JSON.parse(rawText);
        } catch (error) {
            throw new Error(
                `서버 응답을 읽을 수 없습니다.\n\n` +
                `HTTP ${response.status}\n` +
                `${rawText}`
            );
        }
    }

    if (!response.ok) {
        throw new Error(
            data.detail ||
            data.message ||
            `요청에 실패했습니다. (HTTP ${response.status})`
        );
    }

    return data;
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

        alert(data.message || "회원가입이 완료되었습니다.");

    } catch (error) {
        console.error(error);
        alert(error.message);
    }
}


// =========================================================
// LOGIN
// =========================================================

async function loginUser() {
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

        if (data.access_token) {
            setToken(data.access_token);
        }

        alert(data.message || "로그인되었습니다.");

        await checkLogin();

    } catch (error) {
        console.error(error);
        alert(error.message);
    }
}


// =========================================================
// LOGOUT
// =========================================================

function logoutUser() {
    removeToken();

    alert("로그아웃되었습니다.");

    location.reload();
}


// =========================================================
// CURRENT USER
// =========================================================

async function getCurrentUser() {
    const token = getToken();

    if (!token) {
        return null;
    }

    try {
        const response = await fetch(
            `${API_URL}/auth/me`,
            {
                method: "GET",

                headers: {
                    "Authorization": `Bearer ${token}`
                }
            }
        );

        if (!response.ok) {
            removeToken();
            return null;
        }

        return await parseResponse(response);

    } catch (error) {
        console.error(error);
        return null;
    }
}


// =========================================================
// LOGIN STATE
// =========================================================

async function checkLogin() {
    const user = await getCurrentUser();

    const loginButton =
        document.getElementById("loginButton");

    const logoutButton =
        document.getElementById("logoutButton");

    const userInfo =
        document.getElementById("userInfo");

    const adminButton =
        document.getElementById("adminButton");

    if (user) {

        if (loginButton) {
            loginButton.style.display = "none";
        }

        if (logoutButton) {
            logoutButton.style.display = "block";
        }

        if (userInfo) {
            userInfo.textContent =
                `${user.nickname}님`;
        }

        if (adminButton) {
            if (user.is_admin === 1) {
                adminButton.style.display = "block";
            } else {
                adminButton.style.display = "none";
            }
        }

    } else {

        if (loginButton) {
            loginButton.style.display = "block";
        }

        if (logoutButton) {
            logoutButton.style.display = "none";
        }

        if (userInfo) {
            userInfo.textContent = "";
        }

        if (adminButton) {
            adminButton.style.display = "none";
        }
    }
}


// =========================================================
// IMAGE UPLOAD
// =========================================================

async function uploadImage(file) {
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

    return await parseResponse(response);
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
        `${API_URL}/articles`
    );

    return await parseResponse(response);
}


// =========================================================
// GET ARTICLE
// =========================================================

async function getArticle(articleId) {
    const response = await fetch(
        `${API_URL}/articles/${articleId}`
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
// ADMIN USERS
// =========================================================

async function getAdminUsers() {
    const token = getToken();

    if (!token) {
        throw new Error("로그인이 필요합니다.");
    }

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


// =========================================================
// ADMIN MAKE ADMIN
// =========================================================

async function makeAdmin(userId) {
    const token = getToken();

    if (!token) {
        throw new Error("로그인이 필요합니다.");
    }

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


// =========================================================
// ADMIN REMOVE ADMIN
// =========================================================

async function removeAdmin(userId) {
    const token = getToken();

    if (!token) {
        throw new Error("로그인이 필요합니다.");
    }

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


// =========================================================
// ADMIN BAN
// =========================================================

async function banUser(userId) {
    const token = getToken();

    if (!token) {
        throw new Error("로그인이 필요합니다.");
    }

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


// =========================================================
// ADMIN UNBAN
// =========================================================

async function unbanUser(userId) {
    const token = getToken();

    if (!token) {
        throw new Error("로그인이 필요합니다.");
    }

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


// =========================================================
// ADMIN ARTICLES
// =========================================================

async function getAdminArticles() {
    const token = getToken();

    if (!token) {
        throw new Error("로그인이 필요합니다.");
    }

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


// =========================================================
// ADMIN DELETE ARTICLE
// =========================================================

async function adminDeleteArticle(articleId) {
    const token = getToken();

    if (!token) {
        throw new Error("로그인이 필요합니다.");
    }

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
// INITIALIZE
// =========================================================

document.addEventListener(
    "DOMContentLoaded",
    async function () {
        await checkLogin();
    }
);

