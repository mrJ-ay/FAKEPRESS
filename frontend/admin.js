const API_URL = "https://fakepress.onrender.com";

const token =
    localStorage.getItem(
        "fakepress_token"
    );

const currentUser =
    JSON.parse(
        localStorage.getItem(
            "fakepress_current_user"
        ) || "null"
    );


// ============================================================
// 로그인 / 관리자 확인
// ============================================================

if (!token || !currentUser) {

    alert("로그인이 필요합니다.");

    location.href = "index.html";

}

else if (!currentUser.is_admin) {

    alert("관리자만 접근할 수 있습니다.");

    location.href = "index.html";

}

else {

    document.getElementById(
        "adminNickname"
    ).textContent =
        `${currentUser.nickname} 관리자`;

    loadUsers();

    loadArticles();

}


// ============================================================
// 공통 헤더
// ============================================================

function getHeaders() {

    return {

        "Content-Type":
            "application/json",

        "Authorization":
            `Bearer ${token}`

    };

}


// ============================================================
// 메시지
// ============================================================

function showMessage(
    text
) {

    const message =
        document.getElementById(
            "message"
        );

    message.textContent = text;

    message.style.display = "block";

    setTimeout(
        () => {
            message.style.display =
                "none";
        },
        2000
    );

}


// ============================================================
// 회원 목록
// ============================================================

async function loadUsers() {

    const container =
        document.getElementById(
            "userList"
        );

    container.textContent =
        "불러오는 중...";


    try {

        const response =
            await fetch(
                `${API_URL}/admin/users`,
                {
                    headers:
                        getHeaders()
                }
            );


        if (!response.ok) {

            const error =
                await response.json();

            throw new Error(
                error.detail ||
                "회원 목록을 불러오지 못했습니다."
            );

        }


        const users =
            await response.json();


        if (users.length === 0) {

            container.innerHTML =
                `<div class="empty">
                    등록된 회원이 없습니다.
                </div>`;

            return;

        }


        container.innerHTML = `

            <table>

                <thead>

                    <tr>

                        <th>ID</th>

                        <th>닉네임</th>

                        <th>상태</th>

                        <th>가입일</th>

                        <th>관리</th>

                    </tr>

                </thead>

                <tbody>

                    ${users.map(
                        user => renderUser(user)
                    ).join("")}

                </tbody>

            </table>

        `;

    }

    catch (error) {

        console.error(error);

        container.innerHTML =
            `<div class="empty">
                ${escapeHtml(error.message)}
            </div>`;

    }

}


// ============================================================
// 회원 한 명 렌더링
// ============================================================

function renderUser(
    user
) {

    let status = "";

    if (user.is_banned) {

        status =
            `<span class="status-banned">
                정지됨
            </span>`;

    }

    else if (user.is_admin) {

        status =
            `<span class="status-admin">
                관리자
            </span>`;

    }

    else {

        status =
            `<span class="status-normal">
                정상
            </span>`;

    }


    let buttons = "";


    if (user.id === currentUser.id) {

        buttons =
            `<span>
                현재 관리자
            </span>`;

    }

    else {

        const banButton =
            user.is_banned

                ? `
                    <button
                        class="unban"
                        onclick="toggleBan(${user.id})"
                    >
                        정지 해제
                    </button>
                  `

                : `
                    <button
                        class="ban"
                        onclick="toggleBan(${user.id})"
                    >
                        정지
                    </button>
                  `;


        const adminButton =
            user.is_admin

                ? `
                    <button
                        class="remove-admin"
                        onclick="toggleAdmin(${user.id})"
                    >
                        관리자 해제
                    </button>
                  `

                : `
                    <button
                        class="admin"
                        onclick="toggleAdmin(${user.id})"
                    >
                        관리자 지정
                    </button>
                  `;


        buttons =
            banButton +
            " " +
            adminButton;

    }


    return `

        <tr>

            <td>${user.id}</td>

            <td>
                ${escapeHtml(user.nickname)}
            </td>

            <td>
                ${status}
            </td>

            <td>
                ${
                    user.created_at
                    ? new Date(
                        user.created_at
                      ).toLocaleString(
                        "ko-KR"
                      )
                    : "-"
                }
            </td>

            <td>
                ${buttons}
            </td>

        </tr>

    `;

}


// ============================================================
// 회원 정지 / 해제
// ============================================================

async function toggleBan(
    userId
) {

    if (
        !confirm(
            "이 회원의 정지 상태를 변경할까요?"
        )
    ) {
        return;
    }


    try {

        const response =
            await fetch(
                `${API_URL}/admin/users/${userId}/ban`,
                {
                    method: "PUT",
                    headers:
                        getHeaders()
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.detail ||
                "처리 실패"
            );

        }


        showMessage(
            data.message
        );

        loadUsers();

    }

    catch (error) {

        alert(
            error.message
        );

    }

}


// ============================================================
// 관리자 권한 변경
// ============================================================

async function toggleAdmin(
    userId
) {

    if (
        !confirm(
            "이 회원의 관리자 권한을 변경할까요?"
        )
    ) {
        return;
    }


    try {

        const response =
            await fetch(
                `${API_URL}/admin/users/${userId}/admin`,
                {
                    method: "PUT",
                    headers:
                        getHeaders()
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.detail ||
                "처리 실패"
            );

        }


        showMessage(
            data.message
        );

        loadUsers();

    }

    catch (error) {

        alert(
            error.message
        );

    }

}


// ============================================================
// 기사 목록
// ============================================================

async function loadArticles() {

    const container =
        document.getElementById(
            "articleList"
        );

    container.textContent =
        "불러오는 중...";


    try {

        const response =
            await fetch(
                `${API_URL}/admin/articles`,
                {
                    headers:
                        getHeaders()
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.detail ||
                "기사 목록을 불러오지 못했습니다."
            );

        }


        if (data.length === 0) {

            container.innerHTML =
                `<div class="empty">
                    등록된 기사가 없습니다.
                </div>`;

            return;

        }


        container.innerHTML =
            data.map(
                article =>
                    renderArticle(
                        article
                    )
            ).join("");

    }

    catch (error) {

        console.error(error);

        container.innerHTML =
            `<div class="empty">
                ${escapeHtml(error.message)}
            </div>`;

    }

}


// ============================================================
// 기사 렌더링
// ============================================================

function renderArticle(
    article
) {

    return `

        <div class="article-row">

            <div class="article-info">

                <div class="article-title">

                    ${escapeHtml(
                        article.title
                    )}

                </div>

                <div class="article-meta">

                    ID:
                    ${article.id}

                    · 작성자:
                    ${escapeHtml(
                        article.owner_nickname
                    )}

                    · 기자:
                    ${escapeHtml(
                        article.author || "-"
                    )}

                    · 날짜:
                    ${escapeHtml(
                        article.date || "-"
                    )}

                </div>

            </div>


            <div>

                <button
                    class="delete"
                    onclick="deleteArticle(${article.id})"
                >
                    삭제
                </button>

            </div>

        </div>

    `;

}


// ============================================================
// 기사 삭제
// ============================================================

async function deleteArticle(
    articleId
) {

    if (
        !confirm(
            "정말 이 기사를 삭제할까요?"
        )
    ) {
        return;
    }


    try {

        const response =
            await fetch(
                `${API_URL}/articles/${articleId}`,
                {
                    method: "DELETE",
                    headers:
                        getHeaders()
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.detail ||
                "기사 삭제 실패"
            );

        }


        showMessage(
            data.message
        );

        loadArticles();

    }

    catch (error) {

        alert(
            error.message
        );

    }

}


// ============================================================
// HTML 이스케이프
// ============================================================

function escapeHtml(
    value
) {

    if (
        value === null ||
        value === undefined
    ) {
        return "";
    }


    return String(value)
        .replaceAll(
            "&",
            "&amp;"
        )
        .replaceAll(
            "<",
            "&lt;"
        )
        .replaceAll(
            ">",
            "&gt;"
        )
        .replaceAll(
            '"',
            "&quot;"
        )
        .replaceAll(
            "'",
            "&#039;"
        );

}