from django.contrib import admin
from django.urls import path, include, re_path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework import routers
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from core.views import health_check

from emails.views import MailBoxViewSet, EmailMessageViewSet
# from core.views import health_check # Necessário implementar health_check

# Configuração do Swagger/OpenAPI (Jullio)
schema_view = get_schema_view(
   openapi.Info(
      title="Automação de Processos API",
      default_version='v1',
      description="Documentação da API REST para o Backend de Automação com IA.",
      # ... outros metadados
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

# Roteador DRF
router = routers.DefaultRouter()
router.register(r'mailboxes', MailBoxViewSet)
router.register(r'emails', EmailMessageViewSet)

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Health Check e Métricas (Se implementadas no app 'core')
    # path('healthz', health_check, name='healthz'),
    path('healthz/', health_check, name='healthz'),
    # API V1
    path('api/v1/', include(router.urls)),

    # Autenticação JWT (Jullio)
    path('api/v1/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v1/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Documentação OpenAPI/Swagger (Jullio)
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]