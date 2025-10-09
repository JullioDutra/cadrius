# tasks/tasks.py

import os
import logging
from datetime import timedelta
from django.utils import timezone
from django.db import IntegrityError
from django_q.tasks import async_task
import imapclient # Para fetch_emails

from email import policy
from email.parser import BytesParser
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

# Importa os modelos de Jullio
from emails.models import MailBox, EmailMessage, EmailStatus
# Importa a lógica de processamento
from integrations.telegram import notify_telegram # Manter apenas o Telegram
# Removida a importação do Trello: 
# from integrations.trello import create_trello_card 
from extraction.ai_wrapper import extract_fields_from_text 
from extraction.schemas import ServiceOrderSchema 

logger = logging.getLogger(__name__)



# -------------------------------------------------------------------
# Wrapper: mantém o NOME notify_telegram, mas aceita assinaturas diferentes
# notify_telegram("texto")  | notify_telegram(message="texto")
# notify_telegram(chat_id, "texto") usando settings.TELEGRAM_CHAT_ID
# -------------------------------------------------------------------
_notify_orig = notify_telegram 
def notify_telegram(*args, **kwargs):
    """
    Wrapper compatível:
    - aceita notify_telegram("texto")
    - aceita notify_telegram(message="texto")
    - aceita notify_telegram(chat_id, "texto")
    - aceita notify_telegram(email_msg=..., message="texto")
    """
    # importa settings localmente para não mexer nos imports do topo
    try:
        from django.conf import settings as _settings
    except Exception:
        _settings = None

    # tenta chamar do jeito que receberam
    try:
        return _notify_orig(*args, **kwargs)
    except TypeError:
        pass

    # extrai uma mensagem de fallback
    msg = kwargs.get("message")
    if not msg:
        if len(args) == 1 and isinstance(args[0], str):
            msg = args[0]
        elif len(args) >= 2 and isinstance(args[1], str):
            msg = args[1]
        else:
            msg = "Notificação"

    # tenta assinaturas alternativas
    try:
        return _notify_orig(msg)  # notify_telegram("texto")
    except TypeError:
        pass
    try:
        return _notify_orig(message=msg)  # notify_telegram(message="texto")
    except TypeError:
        pass
    try:
        chat_id = getattr(_settings, "TELEGRAM_CHAT_ID", None) if _settings else None
        if chat_id:
            return _notify_orig(chat_id, msg)  # notify_telegram(chat_id, "texto")
    except Exception:
        pass

    logger.warning("Falha ao notificar no Telegram: %s", msg)
    return None


# ----------------- Helpers -----------------
def _decode_str(value: str) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value

def _to_aware(dt):
    if dt is None:
        return timezone.now()
    try:
        if timezone.is_naive(dt):
            return timezone.make_aware(dt, timezone.get_current_timezone())
        return dt
    except Exception:
        return timezone.now()

def _extract_body(email_obj):
    """Prefere text/plain; fallback para qualquer text/*."""
    try:
        if email_obj.is_multipart():
            for part in email_obj.walk():
                ctype = (part.get_content_type() or "").lower()
                disp = (part.get_content_disposition() or "").lower()
                if ctype == "text/plain" and "attachment" not in disp:
                    return (part.get_content() or "").strip()
            # fallback text/*
            for part in email_obj.walk():
                if (part.get_content_type() or "").lower().startswith("text/"):
                    return (part.get_content() or "").strip()
            return ""
        return (email_obj.get_content() or "").strip()
    except Exception:
        return ""

def _safe_int(value, default=None):
    try:
        return int(value)
    except Exception:
        return default

def _model_has_field(model_cls, field_name: str) -> bool:
    try:
        return any(getattr(f, "name", None) == field_name for f in model_cls._meta.get_fields())
    except Exception:
        return False


# ----------------- Atualiza checkpoint -----------------
def _touch_mailbox_checkpoint(mailbox: MailBox, processed_uids):
    update_fields = []

    # marca o momento do último fetch
    if hasattr(mailbox, "last_checked"):
        mailbox.last_checked = timezone.now()
        update_fields.append("last_checked")
    elif hasattr(mailbox, "last_fetch_at"):
        mailbox.last_fetch_at = timezone.now()
        update_fields.append("last_fetch_at")

    # avança last_uid, se existir e houver UIDs processados
    if processed_uids and hasattr(mailbox, "last_uid"):
        try:
            mailbox.last_uid = max([x for x in processed_uids if x is not None])
            if "last_checked" not in update_fields and hasattr(mailbox, "last_checked"):
                update_fields.append("last_checked")
            if "last_fetch_at" not in update_fields and hasattr(mailbox, "last_fetch_at"):
                update_fields.append("last_fetch_at")
        except Exception:
            pass

    if update_fields:
        try:
            mailbox.save(update_fields=update_fields)
        except Exception as e:
            logger.warning("Falha ao atualizar checkpoint da MailBox %s: %s", mailbox.id, e)


# ----------------- FUNÇÃO PRINCIPAL -----------------
def fetch_emails(mailbox_id: int) -> int:
    """
    Lê emails via IMAP e cria EmailMessage para cada mensagem nova.
    - Usa MailBox.imap_host / imap_port / username / password (sem espaços na app password).
    - Pasta padrão: INBOX (campo 'folder' é opcional).
    - Deduplica por UID (se EmailMessage tiver 'uid') e por Message-ID.
    - Atualiza last_fetch_at/last_checked se existirem.
    - Dispara async_task('tasks.process_email', email_msg.id).
    """
    server = None
    processed_uids = []
    total_created = 0

    try:
        mailbox = MailBox.objects.get(id=mailbox_id)

        # ---- Campos reais do seu modelo ----
        
        username = getattr(mailbox, "username", None) or getattr(mailbox, "imap_username", None)
        password = (
            getattr(mailbox, "password", None)
            or getattr(mailbox, "imap_password", None)
            or getattr(mailbox, "app_password", None)
        )
        host = getattr(mailbox, "imap_host", None) or getattr(mailbox, "host", None)
        port = getattr(mailbox, "imap_port", None) or getattr(mailbox, "port", None) or 993
        use_ssl = True if not hasattr(mailbox, "use_ssl") else bool(getattr(mailbox, "use_ssl", True))
        folder = getattr(mailbox, "folder", None) or "INBOX"
        last_uid = getattr(mailbox, "last_uid", None)

                # ---- OVERRIDE via variáveis de ambiente ----
        env_host = os.getenv("IMAP_HOST")
        env_port = os.getenv("IMAP_PORT")
        env_user = os.getenv("IMAP_USERNAME")
        env_pass = os.getenv("IMAP_PASSWORD")

        if env_host:
            host = env_host
        if env_port:
            try:
                port = int(env_port)
            except Exception:
                pass
        if env_user:
            username = env_user
        if env_pass:
            password = env_pass.replace(" ", "")  # remove espaços da app password do Gmail

        # validação
        if not host or not username or not password:
            msg = f"[fetch_emails] MailBox {mailbox_id} incompleta: host/username/password ausentes."
            logger.error(msg)
            notify_telegram(msg)
            return 0

        # ---- Conexão IMAP ----
        server = imapclient.IMAPClient(host, ssl=use_ssl, port=port, timeout=30)
        server.login(username, password)
        server.select_folder(folder, readonly=True)

        # ---- Estratégia de busca ----
        uids = []
        if last_uid is not None:
            try:
                uids = server.search(['UID', f'{int(last_uid) + 1}:*'])
            except Exception as e:
                logger.warning("[fetch_emails] Falha search por UID em MailBox %s: %s", mailbox_id, e)

        if not uids:
            try:
                uids = server.search(['UNSEEN'])
            except Exception as e:
                logger.warning("[fetch_emails] Falha search UNSEEN em MailBox %s: %s", mailbox_id, e)

        if not uids:
            try:
                all_uids = server.search(['ALL'])
                all_uids.sort()
                uids = all_uids[-50:]  # fallback seguro
            except Exception as e:
                logger.error("[fetch_emails] Falha search ALL em MailBox %s: %s", mailbox_id, e)
                uids = []

        if not uids:
            _touch_mailbox_checkpoint(mailbox, processed_uids=False)
            return 0

        # ---- Busca em lotes ----
        BATCH_SIZE = 200
        for i in range(0, len(uids), BATCH_SIZE):
            batch = uids[i:i+BATCH_SIZE]
            fetched = server.fetch(batch, ['RFC822', 'UID', 'FLAGS', 'ENVELOPE'])

            for uid in batch:
                try:
                    data = fetched.get(uid)
                    if not data:
                        continue

                    raw_bytes = data.get(b'RFC822') or data.get('RFC822') \
                                or data.get(b'BODY[]') or data.get('BODY[]')
                    if not raw_bytes:
                        logger.warning("UID %s sem corpo (RFC822/BODY[] ausentes) na MailBox %s", uid, mailbox_id)
                        continue

                    msg = BytesParser(policy=policy.default).parsebytes(raw_bytes)

                    message_id = (msg.get('Message-Id') or msg.get('Message-ID') or "").strip() or None
                    subject = _decode_str(msg.get('Subject'))
                    from_addr = _decode_str(msg.get('From'))
                    to_addr = _decode_str(msg.get('To'))
                    date_hdr = msg.get('Date')

                    try:
                        dt = parsedate_to_datetime(date_hdr) if date_hdr else None
                    except Exception:
                        dt = None
                    date_aware = _to_aware(dt)

                    body_text = _extract_body(msg)

                    # Deduplicação por Message-ID (se o modelo tiver)
                    if message_id and _model_has_field(EmailMessage, "message_id"):
                        try:
                            qs = EmailMessage.objects.filter(message_id=message_id)
                            if _model_has_field(EmailMessage, "mailbox"):
                                qs = qs.filter(mailbox=mailbox)
                            if qs.exists():
                                processed_uids.append(_safe_int(uid))
                                continue
                        except Exception:
                            pass

                    # Monta payload respeitando campos existentes
                    # --- garante message_id não-nulo (alguns emails vêm sem) ---
                    if not message_id:
                        message_id = f"<uid-{int(uid)}@{host}>"

                    # --- Monta payload respeitando os campos do seu modelo ---
                    payload = {}

                    # FK para a mailbox
                    if _model_has_field(EmailMessage, "mailbox"):
                        payload["mailbox"] = mailbox

                    # IDs / cabeçalhos
                    if _model_has_field(EmailMessage, "message_id"):
                        payload["message_id"] = message_id

                    if _model_has_field(EmailMessage, "subject"):
                        payload["subject"] = subject or "(sem assunto)"

                    # REMAPEIA 'From' para o campo obrigatório 'sender'
                    if _model_has_field(EmailMessage, "sender"):
                        payload["sender"] = from_addr
                    elif _model_has_field(EmailMessage, "from_addr"):
                        payload["from_addr"] = from_addr  # caso exista também

                    # REMAPEIA a data para o campo obrigatório 'received_at'
                    if _model_has_field(EmailMessage, "received_at"):
                        payload["received_at"] = date_aware
                    elif _model_has_field(EmailMessage, "date"):
                        payload["date"] = date_aware

                    # Corpo
                    if _model_has_field(EmailMessage, "body_text"):
                        payload["body_text"] = body_text or ""

                    # UID (se existir no modelo)
                    if _model_has_field(EmailMessage, "uid"):
                        payload["uid"] = _safe_int(uid)

                    # Status (se existir e houver enum)
                    if _model_has_field(EmailMessage, "status"):
                        try:
                            status_value = getattr(EmailStatus, "RECEIVED", None) or getattr(EmailStatus, "received", None)
                            if status_value is not None:
                                payload["status"] = status_value
                        except Exception:
                            pass

                    # timestamps obrigatórios (se o modelo não usar auto_now/auto_now_add)
                    now = timezone.now()
                    if _model_has_field(EmailMessage, "created_at"):
                        payload["created_at"] = now
                    if _model_has_field(EmailMessage, "updated_at"):
                        payload["updated_at"] = now

                    try:
                        email_msg = EmailMessage.objects.create(**payload)
                        total_created += 1
                        processed_uids.append(_safe_int(uid))
                        async_task('tasks.process_email', email_msg.id)
                    except IntegrityError:
                        logger.info("Email duplicado (uid=%s, mailbox=%s) - ignorando.", uid, mailbox_id)
                        processed_uids.append(_safe_int(uid))
                        continue
                    except Exception as e:
                        logger.exception("Falha ao criar EmailMessage (UID %s MailBox %s): %s", uid, mailbox_id, e)
                        notify_telegram(f"[fetch_emails] Falha ao salvar email UID {uid} MailBox {mailbox_id}: {e}")
                        continue

                except Exception as e:
                    logger.exception("Erro ao processar UID %s na MailBox %s: %s", uid, mailbox_id, e)
                    notify_telegram(f"[fetch_emails] Erro UID {uid} MailBox {mailbox_id}: {e}")

        _touch_mailbox_checkpoint(mailbox, processed_uids=processed_uids)
        return total_created

    except MailBox.DoesNotExist:
        msg = f"[fetch_emails] MailBox {mailbox_id} não encontrada."
        logger.error(msg)
        notify_telegram(msg)
        return 0
    except imapclient.exceptions.IMAPClientError as e:
        msg = f"[fetch_emails] IMAPClientError MailBox {mailbox_id}: {e}"
        logger.error(msg)
        notify_telegram(msg)
        return 0
    except Exception as e:
        msg = f"[fetch_emails] Erro inesperado MailBox {mailbox_id}: {e}"
        logger.exception(msg)
        notify_telegram(msg)
        return 0
    finally:
        try:
            if server is not None:
                server.logout()
        except Exception:
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