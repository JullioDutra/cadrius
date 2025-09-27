import requests
import os
import logging
from .models import IntegrationLog
from emails.models import EmailMessage # Apenas para typing/FK
from integrations.models import IntegrationLog, IntegrationStatus 

logger = logging.getLogger(__name__)

# Configurações lidas do .env
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
TELEGRAM_BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def notify_telegram(email_msg: EmailMessage, message: str, chat_id: str = None) -> dict:
    """
    Envia uma notificação formatada para o Telegram e registra o log.
    """
    chat_id = chat_id or TELEGRAM_CHAT_ID
    
    log = IntegrationLog.objects.create(
        email_message=email_msg,
        service='TELEGRAM',
        status=IntegrationStatus.PENDING,
        request_data={"chat_id": chat_id, "message": message}
    )
    
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'Markdown'
    }
    
    try:
        response = requests.post(
            f"{TELEGRAM_BASE_URL}/sendMessage",
            data=payload,
            timeout=5
        )
        response.raise_for_status()
        
        # Sucesso
        response_json = response.json()
        log.status = IntegrationStatus.SUCCESS
        log.response_code = response.status_code
        log.response_body = response_json
        log.save()
        
        logger.info("Notificação Telegram enviada com sucesso.")
        return response_json
        
    except requests.exceptions.RequestException as e:
        # Falha
        status_code = getattr(e.response, 'status_code', 500)
        error_details = str(e)
        
        log.status = IntegrationStatus.FAILED
        log.response_code = status_code
        log.response_body = {"error": error_details}
        log.save()
        
        logger.error(f"Falha ao enviar Telegram (Status {status_code}): {error_details}")
        raise