from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from .views import LoginView

urlpatterns = [
    path("login/", csrf_exempt(LoginView.as_view()), name="login"),
    path("token/refresh/", csrf_exempt(TokenRefreshView.as_view()), name="token_refresh"),
    path("token/verify/", csrf_exempt(TokenVerifyView.as_view()), name="token_verify"),
]
