# tasks/tasks.py

import os
import logging
from datetime import timedelta
from django.utils import timezone
from django.db import IntegrityError
from django_q.tasks import async_task
import imapclient # Para fetch_emails

# Importa os modelos de Jullio
from emails.models import MailBox, EmailMessage, EmailStatus
# Importa a lógica de processamento
from integrations.telegram import notify_telegram # Manter apenas o Telegram
# Removida a importação do Trello: 
# from integrations.trello import create_trello_card 
from extraction.ai_wrapper import extract_fields_from_text 
from extraction.schemas import ServiceOrderSchema 

logger = logging.getLogger(__name__)

# --- FUNÇÃO DE BUSCA DE EMAILS (THALES) ---
def fetch_emails(mailbox_id):
    # ... (Conteúdo da função fetch_emails permanece inalterado)
    # Garante que, após salvar o EmailMessage, chama:
    # async_task('tasks.process_email', email_msg.id)
    pass


# --- FUNÇÃO PRINCIPAL DO PIPELINE (THALES) ---

def process_email(email_id):
    """
    Worker principal: coordena a extração de IA e as integrações externas.
    FLUXO ATUALIZADO: Extração -> Persistência -> Notificação Telegram.
    """
    try:
        email = EmailMessage.objects.get(pk=email_id)
        email.status = EmailStatus.PROCESSING
        email.processing_attempts += 1
        email.save()
        
        # 1. EXTRAÇÃO DE DADOS (Juliano)
        logger.info(f"Iniciando extração IA para email ID: {email.id}")
        
        extracted_data = extract_fields_from_text(
            text=email.body_text,
            schema=ServiceOrderSchema, 
            prompt_template="Extraia os campos de pedido a seguir...",
            examples=[]
        )
        
        if extracted_data is None:
            # Fallback (Marcar para Revisão)
            email.status = EmailStatus.REQUIRES_REVIEW
            email.save()
            # Notificação opcional para equipe de QA/Revisão
            notify_telegram(email_msg=email, message=f"Revisão necessária para email ID: {email.id}. Extração IA falhou.")
            return

        email.extracted_data = extracted_data
        email.status = EmailStatus.EXTRACTED
        email.save()
        
        # 2. INTEGRAÇÕES (Thales)
        
        # --- BLOCO TRELLO REMOVIDO/IGNORADO ---
        # Removida a chamada: create_trello_card(extracted_data)
        
        # Telegram (Manter apenas a Notificação)
        logger.info(f"Iniciando notificação Telegram para email ID: {email.id}")
        
        # Montar a mensagem com os dados essenciais
        message = (
            f"**🤖 Novo Processo Automatizado**\n"
            f"**Assunto:** {email.subject}\n"
            f"**Status da Extração:** SUCESSO\n"
            f"**Prioridade Sugerida:** {extracted_data.get('priority', 'N/A')}"
        )
        
        notify_telegram(email_msg=email, message=message) 
        
        # 3. FINALIZAÇÃO
        email.status = EmailStatus.INTEGRATED # O ciclo completo (Extraído + Notificado) foi concluído
        email.last_processed_at = timezone.now()
        email.save()
        
    except EmailMessage.DoesNotExist:
        logger.error(f"EmailMessage {email_id} não encontrado.")
    except Exception as e:
        # Lógica de erro: marcar como FAILED e logar
        email.status = EmailStatus.FAILED
        email.save()
        logger.exception(f"Erro crítico no processamento do email {email_id}: {e}")