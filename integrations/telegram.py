import requests
import os
import logging
from .models import IntegrationLog
from emails.models import EmailMessage # Apenas para typing/FK
from integrations.models import IntegrationLog, IntegrationStatus 

logger = logging.getLogger(__name__)



def notify_telegram(email_msg: EmailMessage, message: str, chat_id: str = None) -> dict:
    """
    Envia uma notificação formatada para o Telegram e registra o log.
    """
    # --- LEIA AS VARIÁVEIS DE AMBIENTE AQUI DENTRO ---
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    
    # Use o chat_id passado como argumento ou pegue do ambiente
    target_chat_id = chat_id or os.environ.get('TELEGRAM_CHAT_ID')
    
    # --- Validação ---
    if not bot_token or not target_chat_id:
        logger.error("Credenciais do Telegram (BOT_TOKEN ou CHAT_ID) não encontradas nas variáveis de ambiente.")
        # Você pode optar por não levantar um erro para não quebrar o fluxo todo
        # e apenas logar, mas por enquanto vamos parar aqui para debugar.
        raise ValueError("Credenciais do Telegram não configuradas.")

    # --- MONTE A URL AQUI DENTRO ---
    base_url = f"https://api.telegram.org/bot{bot_token}"

    log = IntegrationLog.objects.create(
        email_message=email_msg,
        service='TELEGRAM',
        status=IntegrationStatus.PENDING,
        request_data={"chat_id": target_chat_id, "message": message}
    )
    
    payload = {
        'chat_id': target_chat_id,
        'text': message,
        'parse_mode': 'Markdown'
    }
    
    try:
        response = requests.post(
            f"{base_url}/sendMessage",  # Use a URL montada localmente
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