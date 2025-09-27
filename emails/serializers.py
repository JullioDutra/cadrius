from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from emails.models import MailBox, EmailMessage, EmailStatus
from integrations.models import IntegrationLog # Para logs de rastreamento

# --- Serializers de Core/Auth (Jullio) ---

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Personaliza o serializer de login para incluir dados customizados no token, se necessário.
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Adicione claims customizados aqui (ex: 'is_admin')
        # token['is_admin'] = user.is_staff
        return token

# --- Serializers de MailBox (Jullio) ---

class MailBoxSerializer(serializers.ModelSerializer):
    """
    Serializer para o CRUD de MailBox. A senha não deve ser retornada em GET.
    """
    class Meta:
        model = MailBox
        fields = ['id', 'name', 'imap_host', 'imap_port', 'username', 'is_active', 'last_fetch_at']
        read_only_fields = ['last_fetch_at']
        extra_kwargs = {
            # O campo 'password' será escrito (POST/PUT), mas não lido (GET)
            'password': {'write_only': True}
        }

# --- Serializers de EmailMessage e Logs (Jullio/Thales/Juliano) ---

class IntegrationLogSerializer(serializers.ModelSerializer):
    """
    Retorna os logs de integração (Trello/Telegram).
    """
    service_display = serializers.CharField(source='get_service_display', read_only=True)
    
    class Meta:
        model = IntegrationLog
        fields = ['id', 'service_display', 'status', 'response_code', 'attempted_at']
        read_only_fields = fields


class EmailMessageSerializer(serializers.ModelSerializer):
    """
    Serializer principal para listar e detalhar emails.
    Inclui os dados extraídos (Juliano) e os logs de integração (Thales).
    """
    mailbox_name = serializers.CharField(source='mailbox.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    # Rastreamento: Inclui logs de integração aninhados
    integration_logs = IntegrationLogSerializer(many=True, read_only=True)

    class Meta:
        model = EmailMessage
        # Note que 'body_text' pode ser grande, restrinja em list views se necessário.
        fields = [
            'id', 'mailbox_name', 'subject', 'sender', 'received_at', 
            'status', 'status_display', 'processing_attempts', 'last_processed_at',
            'body_text', 'extracted_data', 'integration_logs' 
        ]
        read_only_fields = fields # Todos os campos são de leitura, exceto para ações internas.