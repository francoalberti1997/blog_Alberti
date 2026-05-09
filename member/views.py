from django.contrib.auth import authenticate
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.tokens import RefreshToken
from analytics.track import track


@method_decorator(csrf_exempt, name='dispatch')
class LoginView(APIView):
    authentication_classes = []  # permite acceder sin estar logueado
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {"error": "Username y password requeridos"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(request, username=username, password=password)

        if user is None:
            return Response(
                {"error": "Credenciales inválidas"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Verificar que el usuario esté activo (para dar de baja usuarios)
        if not user.is_active:
            return Response(
                {"error": "Tu cuenta ha sido desactivada. Contactá al administrador."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Generar JWT tokens
        refresh = RefreshToken.for_user(user)

        # Registrar evento de telemetría
        track("login", user=user)

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user_id": user.id,
            "username": user.username
        }, status=status.HTTP_200_OK)