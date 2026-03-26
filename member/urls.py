from django.urls import path
from .views import LoginView
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path("login/", csrf_exempt(LoginView.as_view()), name="login"),
]

