from django.http import JsonResponse

def ping_view(request):
    return JsonResponse({"message": "pong"})

from django.contrib.auth import get_user_model
from django.http import JsonResponse

User = get_user_model()

def create_superuser_view(request):
    username = "franco"
    email = "franco@mail.com"
    password = "franco"

    if User.objects.filter(username=username).exists():
        return JsonResponse(
            {"status": "ok", "detail": "El superusuario ya existe"},
            status=200
        )

    User.objects.create_superuser(
        username=username,
        email=email,
        password=password
    )

    return JsonResponse(
        {"status": "created", "detail": "Superusuario creado correctamente"},
        status=201
    )
