from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

# Status de processamento do email
class EmailStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pendente de Processamento'
    PROCESSING = 'PROCESSING', 'Em Processamento'
    EXTRACTED = 'EXTRACTED', 'Dados Extraídos com Sucesso'
    REQUIRES_REVIEW = 'REVIEW', 'Requer Revisão Humana (IA Falhou)'
    INTEGRATED = 'INTEGRATED', 'Integrado (Trello/Telegram OK)'
    FAILED = 'FAILED', 'Falha Crítica'


class MailBox(models.Model):
    """
    Define a caixa de entrada de onde os emails são buscados.
    Responsabilidade: Jullio (Modelagem) e Thales (Uso no Worker IMAP).
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Nome da Caixa")
    # Para simplificar, armazenaremos as credenciais diretamente aqui, 
    # mas em produção deve-se usar um Secret Manager.
    imap_host = models.CharField(max_length=255)
    imap_port = models.IntegerField(default=993)
    username = models.CharField(max_length=255)
    password = models.CharField(max_length=255) # Campo para a senha
    
    last_fetch_at = models.DateTimeField(null=True, blank=True, verbose_name="Última Busca")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Caixa de Email"
        verbose_name_plural = "Caixas de Email"

    def __str__(self):
        return self.name


class EmailMessage(models.Model):
    """
    Armazena o email capturado e seu status de processamento.
    Serve como a principal tabela de trabalho do sistema.
    """
    mailbox = models.ForeignKey(MailBox, on_delete=models.PROTECT, related_name='emails')
    
    # Metadados do Email (Preenchido por Thales no fetch_emails)
    message_id = models.CharField(max_length=255, unique=True, help_text="ID único do email (para idempotência)")
    subject = models.CharField(max_length=500)
    sender = models.EmailField()
    received_at = models.DateTimeField(verbose_name="Recebido em (Timestamp IMAP)")
    body_text = models.TextField(verbose_name="Corpo do Email (Texto Limpo)")
    
    # Status e Logs
    status = models.CharField(
        max_length=20,
        choices=EmailStatus.choices,
        default=EmailStatus.PENDING
    )
    
    # Dados Extraídos (Preenchido por Juliano após o Wrapper de IA)
    # JSONField é ideal para armazenar a saída do ChatGPT validada pelo Pydantic.
    extracted_data = models.JSONField(
        null=True, blank=True, 
        help_text="Dados chave extraídos pela IA (JSON validado)"
    )
    
    # Controles de Processamento
    processing_attempts = models.IntegerField(default=0)
    last_processed_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Mensagem de Email"
        verbose_name_plural = "Mensagens de Email"
        # Jullio: Adicionar índice no campo 'status' para consultas rápidas
        indexes = [
            models.Index(fields=['status', 'received_at']),
        ]

    def __str__(self):
        return f'[{self.status}] {self.subject} - {self.sender}'

    # Método que Thales pode chamar no pipeline para re-enfileirar
    def re_enqueue_for_processing(self):
        """
        Marca o email para ser re-processado, útil após falhas ou revisão.
        """
        self.status = EmailStatus.PENDING
        self.processing_attempts += 1
        self.save()
        # Thales precisará enfileirar a tarefa aqui:
        # from django_q.tasks import async_task
        # async_task('tasks.process_email', self.id)