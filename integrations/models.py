from django.db import models
from emails.models import EmailMessage # Importa o modelo base de Jullio
from django.utils import timezone

class IntegrationStatus(models.TextChoices):
    SUCCESS = 'SUCCESS', 'Sucesso'
    FAILED = 'FAILED', 'Falha na Integração'
    PENDING = 'PENDING', 'Pendente de Execução'
    RETRIED = 'RETRIED', 'Tentativa de Retry'

class IntegrationLog(models.Model):
    """
    Registra o log de chamadas para serviços externos (Trello, Telegram).
    """
    SERVICE_CHOICES = (
        ('TRELLO', 'Trello Card Creation'),
        ('TELEGRAM', 'Telegram Notification'),
    )
    
    email_message = models.ForeignKey(
        EmailMessage, 
        on_delete=models.CASCADE, 
        related_name='integration_logs',
        help_text="Email que acionou esta integração."
    )
    
    service = models.CharField(max_length=50, choices=SERVICE_CHOICES)
    status = models.CharField(max_length=20, choices=IntegrationStatus.choices, default=IntegrationStatus.PENDING)
    
    # Dados da requisição
    request_data = models.JSONField(null=True, blank=True, help_text="Payload enviado ao serviço externo.")
    
    # Dados da resposta
    response_code = models.IntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True, help_text="Resposta recebida do serviço externo.")
    
    attempted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Log de Integração"
        verbose_name_plural = "Logs de Integração"
        # Thales: Permite a busca rápida pelo email e serviço.
        indexes = [
            models.Index(fields=['email_message', 'service', 'status']),
        ]
    
    def __str__(self):
        return f'[{self.get_service_display()}] {self.status} - Email: {self.email_message.id}'