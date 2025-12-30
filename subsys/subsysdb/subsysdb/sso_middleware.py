import requests
from django.http import JsonResponse, HttpResponseRedirect
from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.sessions.backends.db import SessionStore
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

        # 重點：先檢查是否已有 Django session
        if hasattr(request, 'user') and request.user.is_authenticated:
            logger.info(f"使用者已登入: {request.user.username}")
            return self.get_response(request)

        # 從 URL 參數或 session 取得 SSO token
        sso_token = request.GET.get('sso_token') or request.session.get('sso_token')

        if not sso_token:
            logger.error(f"未取得 SSO token")
            return JsonResponse({
                'error': '未提供 SSO token',
                'message': '請從主系統登入',
                'redirect': f'{self.main_system_url}/login.html'
            }, status=401)

        # 向主系統驗證 token
        try:
            response = requests.post(
                f'{self.main_system_url}/api/auth/verify',
                json={'token': sso_token},
                timeout=5
            )

            if response.status_code != 200:
                logger.error(f"Token 驗證失敗: {response.status_code}")
                request.session.flush()
                return JsonResponse({
                    'error': 'Token 無效',
                    'message': '請重新登入'
                }, status=401)

            user_data = response.json()['user']
            logger.info(f"Token 驗證成功: {user_data['username']}")
            
            # 儲存 SSO 資訊到 session
            request.session['sso_token'] = sso_token
            request.session['sso_user'] = user_data
            
            # 建立或更新 Django User
            django_user = self.get_or_create_user(user_data)
            logger.info(f"Django User 已建立/更新: {django_user.username}")
            
            # 關鍵：手動登入使用者
            login(request, django_user, backend='django.contrib.auth.backends.ModelBackend')
            logger.info(f"Django login() 完成")
            
            # 如果是從 URL 帶 token 進來，重導向移除參數
            if 'sso_token' in request.GET:
                logger.info(f"重導向移除 URL 參數")
                return HttpResponseRedirect(request.path)

        except requests.RequestException as e:
            logger.error(f"連線主系統失敗: {e}")
            return JsonResponse({
                'error': 'SSO 驗證失敗',
                'message': str(e)
            }, status=500)

        # 繼續處理請求
        # logger.info(f"繼續處理請求")
        response = self.get_response(request)
        return response

    def get_or_create_user(self, user_data):
        """根據 SSO 資訊建立或更新 Django User"""
        username = user_data['username']
        
        try:
            user = User.objects.get(username=username)
            # 更新使用者資訊
            user.email = user_data.get('email', '')
            user.first_name = user_data.get('first_name', '')
            user.last_name = user_data.get('last_name', '')
            user.is_active = user_data.get('is_active', True)
            user.is_staff = True  # 允許訪問 admin
            user.save()
            logger.info(f"已更新使用者: {username}")
        except User.DoesNotExist:
            # 建立新使用者
            logger.warning(f"使用者[{username}]不存在，正在建立使用者..")
            user = User.objects.create_user(
                username=username,
                email=user_data.get('email', ''),
                first_name=user_data.get('first_name', ''),
                last_name=user_data.get('last_name', ''),
                is_active=user_data.get('is_active', True),
                is_staff=True,  # 允許訪問 admin
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