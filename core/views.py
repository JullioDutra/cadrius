from django.http import JsonResponse
from django.db import connection
from django.shortcuts import render, redirect
from rest_framework.views import APIView 
from rest_framework.response import Response 
from rest_framework import status 
from rest_framework.permissions import AllowAny, IsAuthenticated 

from emails.serializers import UserRegistrationSerializer, UserProfileSerializer

# --- 1. VIEWS DE NAVEGAÇÃO (FRONTEND) ---

def login_view(request):
    """
    Renderiza a tela de login (login.html).
    Rota: /
    """
    # Se o usuário já estiver autenticado (via sessão do Django Admin ou similar),
    # podemos redirecionar, mas como usamos JWT no front, apenas servimos o HTML.
    return render(request, 'login.html')

def register_view(request):
    """
    Renderiza a tela de cadastro (register.html).
    Rota: /register/
    """
    return render(request, 'register.html')

def dashboard_view(request):
    """
    Renderiza o painel principal (dashboard.html).
    Rota: /dashboard/
    """
    return render(request, 'dashboard.html')

# --- 2. VIEWS DE API (BACKEND) ---

def health_check(request):
    """
    Verifica a saúde do serviço e a conectividade com o banco de dados.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"
        return JsonResponse({"status": "error", "db_status": db_status}, status=500)

    return JsonResponse({
        "status": "ok",
        "db_status": db_status,
        "app_version": "v1.0.0"
    })

class RegisterUserView(APIView):
    """
    Endpoint de cadastro de novos usuários.
    """
    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {"detail": "Usuário criado com sucesso.", "user_id": user.id}, 
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class GetUserProfileView(APIView):
    """
    Endpoint para retornar os dados do usuário logado (protegido por JWT).
    """
    permission_classes = [IsAuthenticated] 

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)