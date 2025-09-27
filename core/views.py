# core/views.py

from django.http import JsonResponse
from django.db import connection

def health_check(request):
    """
    Verifica a saúde do serviço e a conectividade com o banco de dados.
    """
    try:
        # Tenta executar uma consulta simples no banco de dados
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"
        # Se o DB falhar, retorna 500
        return JsonResponse({
            "status": "error",
            "db_status": db_status
        }, status=500)

    # Se tudo estiver OK, retorna 200
    return JsonResponse({
        "status": "ok",
        "db_status": db_status,
        "app_version": "v1.0.0" # Adicione sua versão de aplicação
    })