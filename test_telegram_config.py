#!/usr/bin/env python3
"""
Teste para verificar as configurações do Telegram
"""

import os
import sys
import django

# Configura o Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cadrius.settings')
django.setup()

def test_telegram_config():
    """Testa as configurações do Telegram"""
    print("TESTE DE CONFIGURACAO DO TELEGRAM")
    print("=" * 50)
    
    # Verifica variáveis de ambiente
    print("\n=== VARIAVEIS DE AMBIENTE ===")
    telegram_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    print(f"TELEGRAM_BOT_TOKEN: {'Configurado' if telegram_token else 'Nao configurado'}")
    if telegram_token:
        print(f"Token (primeiros 10 chars): {telegram_token[:10]}...")
    
    print(f"TELEGRAM_CHAT_ID: {'Configurado' if telegram_chat_id else 'Nao configurado'}")
    if telegram_chat_id:
        print(f"Chat ID: {telegram_chat_id}")
    
    # Testa importação do módulo telegram
    print("\n=== TESTE DE IMPORTACAO ===")
    try:
        from integrations.telegram import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_BASE_URL
        print("Importacao do modulo telegram: OK")
        print(f"TELEGRAM_BOT_TOKEN no modulo: {'Configurado' if TELEGRAM_BOT_TOKEN else 'Nao configurado'}")
        print(f"TELEGRAM_CHAT_ID no modulo: {'Configurado' if TELEGRAM_CHAT_ID else 'Nao configurado'}")
        print(f"TELEGRAM_BASE_URL: {TELEGRAM_BASE_URL}")
    except Exception as e:
        print(f"Erro na importacao: {e}")
    
    # Testa envio de mensagem simples
    print("\n=== TESTE DE ENVIO ===")
    if telegram_token and telegram_chat_id:
        try:
            import requests
            
            url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
            payload = {
                'chat_id': telegram_chat_id,
                'text': 'Teste do sistema Cadrius - Configuracao OK!',
                'parse_mode': 'Markdown'
            }
            
            response = requests.post(url, data=payload, timeout=10)
            print(f"Status da resposta: {response.status_code}")
            
            if response.status_code == 200:
                print("SUCESSO: Mensagem enviada para o Telegram!")
                print(f"Resposta: {response.json()}")
            else:
                print(f"ERRO: {response.status_code}")
                print(f"Resposta: {response.text}")
                
        except Exception as e:
            print(f"Erro no envio: {e}")
    else:
        print("Credenciais nao configuradas - pulando teste de envio")
    
    print("\n" + "=" * 50)
    print("Teste concluido!")

if __name__ == "__main__":
    test_telegram_config()
