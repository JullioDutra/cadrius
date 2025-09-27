import os
import logging
import imapclient
from datetime import timedelta
from django.utils import timezone
from django.db import IntegrityError
from django_q.tasks import async_task

# Importa os modelos de Jullio
from emails.models import MailBox, EmailMessage, EmailStatus
# Importa a lógica de processamento que será chamada (ainda é um template)
# from tasks.tasks import process_email # O process_email está neste mesmo arquivo, não precisa de import circular

# Imports de Thales/Juliano
from integrations.trello import create_trello_card # A ser implementado por Thales
from integrations.telegram import notify_telegram # A ser implementado por Thales
from extraction.ai_wrapper import extract_fields_from_text # A ser implementado por Juliano
from extraction.schemas import ServiceOrderSchema # Exemplo de Schema de Juliano

logger = logging.getLogger(__name__)

# --- FUNÇÃO PRINCIPAL DO PIPELINE (THALES) ---

def fetch_emails(mailbox_id):
    """
    Worker que se conecta a uma caixa de email via IMAP, busca novas mensagens
    e as enfileira para processamento.
    Gatilho: Executado periodicamente pelo Django-Q Scheduler (Beat).
    """
    try:
        mailbox = MailBox.objects.get(pk=mailbox_id, is_active=True)
    except MailBox.DoesNotExist:
        logger.error(f"MailBox {mailbox_id} não encontrada ou inativa. Pulando busca.")
        return

    logger.info(f"Iniciando busca IMAP em: {mailbox.name}")
    
    # 1. Conexão IMAP
    try:
        # Usamos SSL/TLS por padrão (Porta 993)
        server = imapclient.IMAPClient(mailbox.imap_host, port=mailbox.imap_port, ssl=True)
        server.login(mailbox.username, mailbox.password)
        server.select_folder('INBOX') 

    except imapclient.exceptions.IMAPClientError as e:
        logger.error(f"Falha na conexão IMAP para {mailbox.name}: {e}")
        return
    except Exception as e:
        logger.error(f"Erro inesperado na conexão para {mailbox.name}: {e}")
        return

    # 2. Busca por Emails (Exemplo: emails dos últimos 7 dias que ainda não foram lidos)
    # A busca deve ser otimizada para minimizar o volume
    # Busca por emails não lidos (UNSEEN)
    search_criteria = ['UNSEEN'] 
    
    # Busca por emails recebidos nos últimos 7 dias (Exemplo)
    # search_criteria.append('SINCE')
    # search_criteria.append((timezone.now() - timedelta(days=7)).strftime('%d-%b-%Y'))
    
    try:
        messages_ids = server.search(search_criteria)
        logger.info(f"Encontrados {len(messages_ids)} emails para processamento.")

        if not messages_ids:
            # Atualiza o timestamp mesmo que não tenha emails (para controle)
            mailbox.last_fetch_at = timezone.now()
            mailbox.save()
            server.logout()
            return
            
        # 3. Fetch dos Dados Essenciais
        # RFC822.HEADER para metadados, BODY[TEXT] para o corpo do texto
        response = server.fetch(messages_ids, ['RFC822.HEADER', 'BODY[TEXT]', 'INTERNALDATE'])
        
        for msg_id, data in response.items():
            try:
                # O imapclient retorna os dados brutos, é necessário parsear
                header = imapclient.parse.get_message_header(data[b'RFC822.HEADER'])
                body_text_bytes = data.get(b'BODY[TEXT]')
                
                # Decodifica o corpo para texto limpo
                body_text = body_text_bytes.decode('utf-8', errors='ignore') if body_text_bytes else ""
                
                # Jullio: Critério de Idempotência
                message_unique_id = header.get('message-id', [None])[0] 
                if not message_unique_id:
                     # Se não tiver ID (emails malformados), use algo único
                     message_unique_id = f"IMAP_NO_ID_{msg_id}_{mailbox.id}"
                     
                
                email_msg = EmailMessage.objects.create(
                    mailbox=mailbox,
                    message_id=message_unique_id, # Chave de Idempotência (Jullio)
                    subject=header.get('subject', ['N/A'])[0] or 'N/A',
                    sender=header.get('from', ['N/A'])[0].split('<')[-1].replace('>', '').strip(),
                    received_at=data.get(b'INTERNALDATE', timezone.now()),
                    body_text=body_text[:EmailMessage._meta.get_field('body_text').max_length], # Garante que não exceda o limite do campo
                    status=EmailStatus.PENDING
                )
                
                # 4. Enfileiramento da Próxima Tarefa (Worker de Processamento)
                async_task('tasks.process_email', email_msg.id)
                server.add_flags(msg_id, [imapclient.imap_utf7.encode('SEEN')]) # Marca como lido após enfileirar
                logger.info(f"Email {msg_id} enfileirado para processamento. ID: {email_msg.id}")

            except IntegrityError:
                # O message_id já existe, ignora (Idempotência OK)
                logger.warning(f"Email com ID {message_unique_id} já existe. Ignorado.")
                continue
            except Exception as e:
                logger.error(f"Erro ao processar email ID {msg_id}: {e}")
                # Loga o erro, mas continua para o próximo email

        # 5. Finalização
        mailbox.last_fetch_at = timezone.now()
        mailbox.save()
        server.logout()
        
    except Exception as e:
        logger.critical(f"Erro fatal na busca IMAP para {mailbox.name}: {e}")
    finally:
        # Garante que a conexão seja fechada em caso de falha
        if 'server' in locals() and server.has_capability('ID'): 
            server.logout()
            
# --- TEMPLATE DO WORKER DE PROCESSAMENTO (JULIANO & THALES) ---
# Esta função já foi detalhada antes, mantida aqui para contexto.

def process_email(email_id):
    """
    Worker principal: coordena a extração de IA e as integrações externas.
    (Conteúdo detalhado em passo anterior)
    """
    try:
        email = EmailMessage.objects.get(pk=email_id)
        # ... Lógica de Juliano (extract_fields_from_text)
        # ... Lógica de Thales (create_trello_card, notify_telegram, IntegrationLog)
        
    except EmailMessage.DoesNotExist:
        logger.error(f"EmailMessage {email_id} não encontrado.")
    except Exception as e:
        # Tratar erros e marcar email como FAILED ou acionar retry
        pass