document.getElementById('login-btn').addEventListener('click', login);

async function login() {
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value.trim();
    const errorMsg = document.getElementById('error-msg');

    errorMsg.textContent = '';

    if (!username || !password) {
        errorMsg.textContent = '請輸入帳號與密碼';
        return;
    }

    try {
        // 改這裡：API 路徑改成 /api/auth/login
        const response = await fetch('http://172.27.207.106:8001/api/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username: username,
                password: password
            })
        });

        const data = await response.json();

        if (!response.ok) {
            errorMsg.textContent = data.detail || '登入失敗';
            console.error(data.detail);
            return;
        }
        // // 新增：儲存 token 到 localStorage
        // localStorage.setItem('access_token', data.access_token);
        // if (data.refresh_token) {
        //     localStorage.setItem('refresh_token', data.refresh_token);
        // }
        localStorage.setItem('access_token', data.session_token);
        
        // 新增：儲存使用者資訊
        localStorage.setItem('user', JSON.stringify(data.user));

        console.log('login success:', data);

        // alert('登入成功');
        
        // 跳轉到儀表板
        window.location.href = '/sso-login.html';

    } catch (err) {
        console.error(err);
        errorMsg.textContent = '無法連線到伺服器';
    }
}