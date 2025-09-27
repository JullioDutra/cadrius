from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from emails.models import MailBox, EmailMessage, EmailStatus
from emails.serializers import MailBoxSerializer, EmailMessageSerializer
from tasks.tasks import process_email # Importa a função do worker de Thales
from django_q.tasks import async_task
from django.db.models import Q

class MailBoxViewSet(viewsets.ModelViewSet):
    """
    Endpoints: /api/v1/mailboxes/ - CRUD de caixas de e-mail.
    """
    queryset = MailBox.objects.all().order_by('name')
    serializer_class = MailBoxSerializer
    permission_classes = [IsAuthenticated] # Exemplo: apenas autenticados podem gerenciar

class EmailMessageViewSet(mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    Endpoints: /api/v1/emails/ - Listagem, Detalhe e Reprocessamento de mensagens.
    """
    queryset = EmailMessage.objects.all().order_by('-received_at')
    serializer_class = EmailMessageSerializer
    permission_classes = [IsAuthenticated]

    # Jullio: Implementação de Filtros Básicos (Critério de Aceite)
    def get_queryset(self):
        queryset = super().get_queryset()
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