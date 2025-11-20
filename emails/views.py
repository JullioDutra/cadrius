from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

# NOVO: Importa os modelos de configuração
from emails.models import MailBox, EmailMessage, EmailStatus, AutomationRule 
from integrations.models import IntegrationConfig
from extraction.models import ExtractionProfile

from emails.serializers import (
    MailBoxSerializer, EmailMessageSerializer, 
    IntegrationConfigSerializer, ExtractionProfileSerializer, AutomationRuleSerializer # NOVO: Serializers
)
from tasks.tasks import process_email 
from django_q.tasks import async_task
from django.db.models import Q

from django_q.models import Schedule

class MailBoxViewSet(viewsets.ModelViewSet):
    """
    Endpoints: /api/v1/mailboxes/ - CRUD de caixas de e-mail (Filtrado por usuário).
    """
    # CORREÇÃO CRÍTICA PARA O DRF ROUTER
    queryset = MailBox.objects.all() 
    
    serializer_class = MailBoxSerializer
    permission_classes = [IsAuthenticated] 

    def get_queryset(self):
        # FILTRO DE MULTI-TENANCY: Apenas caixas de e-mail do usuário logado
        if self.request.user.is_superuser: # Opcional: superusuários veem tudo
            return MailBox.objects.all().order_by('name')
        return MailBox.objects.filter(user=self.request.user).order_by('name')

    def perform_create(self, serializer):
            # 1. Salva a MailBox (necessário para obter o ID)
            mailbox = serializer.save(user=self.request.user) # Jullio: Salva a MailBox

            # 2. Thales: Agenda a tarefa fetch_emails no Django-Q
            Schedule.objects.create(
                func='tasks.tasks.fetch_emails', # A task a ser executada
                args=f'{mailbox.id}', # Argumento da task (o ID da MailBox)
                schedule_type=Schedule.MINUTES,
                minutes=5, # Executa a cada 5 minutos
                name=f'Fetch - MailBox {mailbox.id} ({mailbox.name})',
                # Opcional: Garantir que a tarefa seja removida após falhas críticas
                # cluster='DjangORM' # Referência ao Q_CLUSTER em settings.py
            )

    def perform_destroy(self, instance):
            # 1. Thales: Busca e deleta a tarefa agendada associada
            # Usa o ID da MailBox como argumento para encontrar a tarefa
            Schedule.objects.filter(
                func='tasks.tasks.fetch_emails',
                args=f'{instance.id}',
            ).delete()
            
            # 2. Jullio: Deleta a MailBox
            instance.delete()

class EmailMessageViewSet(mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    Endpoints: /api/v1/emails/ - Listagem, Detalhe e Reprocessamento de mensagens (Filtrado por usuário).
    """
    # CORREÇÃO CRÍTICA PARA O DRF ROUTER
    queryset = EmailMessage.objects.all()
    
    serializer_class = EmailMessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # FILTRO DE MULTI-TENANCY: Apenas e-mails das caixas do usuário logado
        if self.request.user.is_superuser:
            queryset = EmailMessage.objects.all().order_by('-received_at')
        else:
            # Filtra e-mails onde a MailBox.user é o usuário logado
            queryset = EmailMessage.objects.filter(
                mailbox__user=self.request.user 
            ).order_by('-received_at')
        
        # Lógica de filtros existentes (status e busca por q)
        status_filter = self.request.query_params.get('status')
        search_query = self.request.query_params.get('q')

        if status_filter:
            queryset = queryset.filter(status=status_filter.upper())
        
        if search_query:
            # Filtro por assunto ou remetente
            queryset = queryset.filter(
                Q(subject__icontains=search_query) | 
                Q(sender__icontains=search_query)
            )
        return queryset

    # Jullio: Endpoint de Ação Customizada (Reprocessamento)
    @action(detail=True, methods=['post'], url_path='reprocess')
    def reprocess(self, request, pk=None):
        """
        Marca um email para ser re-processado (enfileira novamente a tarefa).
        Endpoint: POST /api/v1/emails/{id}/reprocess/
        """
        try:
            email = self.get_object()
        except EmailMessage.DoesNotExist:
            return Response({"detail": "Email não encontrado."}, status=status.HTTP_404_NOT_FOUND)

        # Atualiza status e tentativas no DB (Jullio)
        email.re_enqueue_for_processing() # Método do Model
        
        # Thales: Enfileira a tarefa no Django-Q
        async_task('tasks.process_email', email.id)

        return Response({
            "detail": "Email enfileirado para reprocessamento.",
            "new_status": email.status_display
        }, status=status.HTTP_202_ACCEPTED)
        
class IntegrationConfigViewSet(viewsets.ModelViewSet):
    """
    Endpoints: /api/v1/integration-configs/ - CRUD de credenciais de integração.
    """
    queryset = IntegrationConfig.objects.all()
    serializer_class = IntegrationConfigSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # FILTRO DE MULTI-TENANCY
        if self.request.user.is_superuser:
            return IntegrationConfig.objects.all().order_by('name')
        return IntegrationConfig.objects.filter(user=self.request.user).order_by('name')

    def perform_create(self, serializer):
        # GARANTE QUE O USUÁRIO LOGADO SEJA O PROPRIETÁRIO
        serializer.save(user=self.request.user)

class ExtractionProfileViewSet(viewsets.ModelViewSet):
    """
    Endpoints: /api/v1/extraction-profiles/ - CRUD de perfis de IA (Prompt e Schema).
    """
    queryset = ExtractionProfile.objects.all()
    serializer_class = ExtractionProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # FILTRO DE MULTI-TENANCY
        if self.request.user.is_superuser:
            return ExtractionProfile.objects.all().order_by('name')
        return ExtractionProfile.objects.filter(user=self.request.user).order_by('name')

    def perform_create(self, serializer):
        # GARANTE QUE O USUÁRIO LOGADO SEJA O PROPRIETÁRIO
        serializer.save(user=self.request.user)

class AutomationRuleViewSet(viewsets.ModelViewSet):
    """
    Endpoints: /api/v1/automation-rules/ - CRUD das regras de automação.
    """
    queryset = AutomationRule.objects.all()
    serializer_class = AutomationRuleSerializer
    permission_classes = [IsAuthenticated]
    
    # Customiza o queryset para permitir filtros de mailbox
    def get_queryset(self):
        queryset = AutomationRule.objects.all().order_by('priority', 'name')
        
        # FILTRO DE MULTI-TENANCY: Apenas regras criadas pelo usuário.
        if not self.request.user.is_superuser:
            queryset = queryset.filter(user=self.request.user)
            
        # Filtro opcional: filtrar por mailbox
        mailbox_id = self.request.query_params.get('mailbox_id')
        if mailbox_id:
            # Garante que a mailbox pertence ao usuário
            if not self.request.user.is_superuser:
                queryset = queryset.filter(mailbox__id=mailbox_id, mailbox__user=self.request.user)
            else:
                queryset = queryset.filter(mailbox__id=mailbox_id)
            
        return queryset

    def perform_create(self, serializer):
        # GARANTE QUE O USUÁRIO LOGADO SEJA O PROPRIETÁRIO
        serializer.save(user=self.request.user)