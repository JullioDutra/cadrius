from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from emails.models import MailBox, EmailMessage, EmailStatus, AutomationRule # NOVO: AutomationRule
from integrations.models import IntegrationLog, IntegrationConfig # NOVO: IntegrationConfig
from extraction.models import ExtractionProfile
from django.contrib.auth import get_user_model

# --- Serializers de Core/Auth (Jullio) ---

User = get_user_model()

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
    Serializer para o CRUD de MailBox.
    """
    # NOVO: Adiciona campos de FK customizados para visualização
    integration_config_name = serializers.CharField(source='integration_config.name', read_only=True)
    extraction_profile_name = serializers.CharField(source='extraction_profile.name', read_only=True)
    
    class Meta:
        model = MailBox
        fields = ['id', 'name', 'imap_host', 'imap_port', 'username', 'is_active', 'last_fetch_at', 
                  'integration_config', 'extraction_profile', 'integration_config_name', 'extraction_profile_name', 'user']
        read_only_fields = ['last_fetch_at', 'user', 'integration_config_name', 'extraction_profile_name']
        extra_kwargs = {
            'password': {'write_only': True}
        }

# --- Serializers de Configuração (NOVO) ---

class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para retornar os dados do usuário logado.
    """
    initials = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'initials']
        read_only_fields = fields

    def get_initials(self, obj):
        """Calcula as iniciais do usuário."""
        if obj.first_name and obj.last_name:
            return f"{obj.first_name[0]}{obj.last_name[0]}".upper()
        if obj.first_name:
            return obj.first_name[0].upper()
        if obj.email:
             return obj.email[0].upper()
        return "U" # Fallback para 'Usuário'

class IntegrationConfigSerializer(serializers.ModelSerializer):
    """
    Serializer para o CRUD de IntegrationConfig (Trello/Telegram keys).
    """
    class Meta:
        model = IntegrationConfig
        # user é read_only e setado no ViewSet
        fields = ['id', 'name', 'trello_api_key', 'trello_api_token', 'trello_list_id', 
                  'telegram_bot_token', 'telegram_chat_id', 'is_active', 'user']
        read_only_fields = ['user']
        extra_kwargs = {
            # Credenciais são de escrita apenas, por segurança
            'trello_api_token': {'write_only': True},
            'telegram_bot_token': {'write_only': True},
        }

class ExtractionProfileSerializer(serializers.ModelSerializer):
    """
    Serializer para o CRUD de ExtractionProfile (Prompt + Schema Pydantic).
    """
    class Meta:
        model = ExtractionProfile
        fields = ['id', 'name', 'system_prompt_template', 'pydantic_schema_name', 'user']
        read_only_fields = ['user']

class AutomationRuleSerializer(serializers.ModelSerializer):
    """
    Serializer para o CRUD de AutomationRule (Regras de automação).
    """
    # Para melhor visualização dos FKs
    mailbox_name = serializers.CharField(source='mailbox.name', read_only=True)
    extraction_profile_name = serializers.CharField(source='extraction_profile.name', read_only=True)

    class Meta:
        model = AutomationRule
        fields = [
            'id', 
            'name', 
            'mailbox', 
            'mailbox_name', 
            'priority', 
            'is_active', 
            'subject_contains', 
            'sender_contains', 
            'extraction_profile', 
            'extraction_profile_name', 
            'action_config', 
            'user'
        ]
        
        read_only_fields = [
            'id', 
            'user', 
            'mailbox', 
            'mailbox_name', 
            'extraction_profile', 
            'extraction_profile_name'
        ]


class CommunicationFlowRuleSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para regras de automação dentro do fluxo de comunicação.
    """
    extraction_profile_name = serializers.CharField(source='extraction_profile.name', read_only=True, default=None)

    class Meta:
        model = AutomationRule
        fields = ['id', 'name', 'is_active', 'priority', 'extraction_profile_name']


class CommunicationFlowSerializer(serializers.ModelSerializer):
    """
    Serializer principal para a tela de "Comunicação".
    Mostra a Mailbox e suas regras de automação aninhadas.
    """
    rules = CommunicationFlowRuleSerializer(many=True, read_only=True)
    
    integration_config_name = serializers.CharField(source='integration_config.name', read_only=True, default=None)

    class Meta:
        model = MailBox
        fields = ['id', 'name', 'is_active', 'integration_config_name', 'rules']


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

    integration_logs_ext = IntegrationLogSerializer(
            source='integration_logs_ext', 
            many=True, 
            read_only=True
        )

    class Meta:
            model = EmailMessage
            # Note que 'body_text' pode ser grande, restrinja em list views se necessário.
            fields = [
                'id', 'mailbox_name', 'subject', 'sender', 'received_at', 
                'status', 'status_display', 'processing_attempts', 'last_processed_at',
                'body_text', 'extracted_data', 'integration_logs_ext' # <--- CAMPO ATUALIZADO
            ]
            read_only_fields = fields
            
            
class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer para criação de um novo usuário.
    Assume que o 'email' será usado como 'username' para login.
    """
    # Campo para o email (requerido e de escrita apenas)
    email = serializers.EmailField(write_only=True, required=True, label="E-mail")
    # Campo para a senha (requerido e de escrita apenas)
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        model = User
        # Incluímos 'username' apenas para compatibilidade, mas o email será usado
        fields = ('id', 'email', 'password', 'first_name', 'last_name')
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def validate(self, data):
        # Usamos o campo 'email' para preencher o 'username' (padrão do Django)
        if User.objects.filter(username=data['email']).exists():
            raise serializers.ValidationError({"email": "Este e-mail já está sendo usado."})
        
        data['username'] = data['email']
        return data

    def create(self, validated_data):
        # Usa o método create_user para garantir que a senha seja hashed (segurança)
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
        )
        return user