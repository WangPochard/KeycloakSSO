import requests
from django.http import HttpResponse, HttpResponseRedirect
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.auth import get_user_model, login
from logging import getLogger

logger = getLogger(__name__)
User = get_user_model()

class SSOMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.main_system_url = settings.MAIN_SYSTEM_URL
        logger.info(f"SSO Middleware 已載入，主系統: {self.main_system_url}")

    def __call__(self, request):
        # 排除公開路徑
        if self.is_public_path(request.path):
            return self.get_response(request)

        # 先檢查是否已登入
        if hasattr(request, 'user') and request.user.is_authenticated:
            logger.info(f"使用者已登入: {request.user.username}")
            return self.get_response(request)

        # 1. 先從 URL 取 token
        token_from_url = request.GET.get('token')
        
        # 2. 如果 URL 有 token,立即存到 session 並重定向
        if token_from_url:
            logger.info(f"從 URL 取得 token: {token_from_url[:20]}...")
            request.session['sso_token'] = token_from_url
            request.session.modified = True
            logger.info("Token 已存到 session,重定向移除 URL 參數")
            return HttpResponseRedirect(request.path)
        
        # 3. 從 session 取 token
        sso_token = request.session.get('sso_token')
        
        if not sso_token:
            logger.error("未取得 sso token")
            return self.render_error_page(
                request,
                '未提供 sso token',
                '請從主系統登入',
                'http://172.27.207.106/sso-login.html'
            )

        logger.info(f'從 session 取得 token,開始驗證')

        # 4. 向主系統驗證 token
        try:
            response = requests.post(
                f'{self.main_system_url}/api/auth/verify',
                json={'token': sso_token},
                timeout=5
            )

            if response.status_code != 200:
                logger.error(f"Token 驗證失敗: {response.status_code}")
                request.session.flush()
                return self.render_error_page(
                    request,
                    'Token 無效',
                    '請重新登入',
                    'http://172.27.207.106/sso-login.html'
                )

            user_data = response.json()['user']
            logger.info(f"Token 驗證成功: {user_data['username']}")
            
            # 5. 建立或更新 Django User
            django_user = self.get_or_create_user(user_data)
            
            # 6. 登入使用者
            login(request, django_user, backend='django.contrib.auth.backends.ModelBackend')
            logger.info(f"使用者 {django_user.username} 已登入")

        except requests.RequestException as e:
            logger.error(f"連線主系統失敗: {e}")
            request.session.flush()
            return self.render_error_page(
                request,
                'SSO 驗證失敗',
                '無法連線到主系統',
                'http://172.27.207.106/sso-login.html'
            )
        except Exception as e:
            logger.error(f"驗證過程錯誤: {e}")
            import traceback
            traceback.print_exc()
            request.session.flush()
            return self.render_error_page(
                request,
                '驗證失敗',
                str(e),
                'http://172.27.207.106/sso-login.html'
            )

        # 7. 繼續處理請求
        response = self.get_response(request)
        return response

    def render_error_page(self, request, error_title, error_message, redirect_url):
        """使用模板渲染 HTML 錯誤頁面"""
        html_content = render_to_string(
            'sso_error.html',
            {
                'error_title': error_title,
                'error_message': error_message,
                'redirect_url': redirect_url,
            },
            request=request
        )
        return HttpResponse(html_content, status=401)

    def get_or_create_user(self, user_data):
        """根據 SSO 資訊建立或更新 Django User"""
        username = user_data['username']
        
        try:
            user = User.objects.get(username=username)
            user.email = user_data.get('email', '')
            user.first_name = user_data.get('first_name', '')
            user.last_name = user_data.get('last_name', '')
            user.is_active = user_data.get('is_active', True)
            user.is_staff = True
            user.save()
            logger.info(f"已更新使用者: {username}")
        except User.DoesNotExist:
            user = User.objects.create_user(
                username=username,
                email=user_data.get('email', ''),
                first_name=user_data.get('first_name', ''),
                last_name=user_data.get('last_name', ''),
                is_active=user_data.get('is_active', True),
                is_staff=True,
            )
            logger.info(f"已建立新使用者: {username}")
        
        return user

    def is_public_path(self, path):
        """不需要驗證的路徑"""
        public_paths = [
            '/static/',
            '/media/',
            '/health/',
            '/favicon.ico',
        ]
        return any(path.startswith(p) for p in public_paths)