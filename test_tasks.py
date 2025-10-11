#!/usr/bin/env python3
"""
Teste para validar o funcionamento do tasks.py
"""

import os
import sys
import django
from datetime import datetime

# Configura o Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cadrius.settings')
django.setup()

from tasks.tasks import fetch_emails, process_email
from emails.models import MailBox, EmailMessage, EmailStatus
from extraction.ai_wrapper import get_extraction_stats

def test_tasks_functionality():
    """Testa as funcoes principais do tasks.py"""
    print("TESTE DO TASKS.PY - CADRIUS")
    print("=" * 50)
    
    # Mostra estatisticas do sistema
    print("\n=== ESTATISTICAS DO SISTEMA ===")
    stats = get_extraction_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    # Verifica se existem MailBoxes configuradas
    print("\n=== VERIFICACAO DE MAILBOXES ===")
    mailboxes = MailBox.objects.all()
    print(f"Numero de MailBoxes encontradas: {mailboxes.count()}")
    
    if mailboxes.exists():
        for mailbox in mailboxes:
            print(f"MailBox ID: {mailbox.id}")
            print(f"Name: {mailbox.name}")
            print(f"Host: {mailbox.imap_host}")
            print(f"Username: {mailbox.username}")
            print(f"Port: {mailbox.imap_port}")
            print(f"Last fetch: {mailbox.last_fetch_at}")
            print(f"Active: {mailbox.is_active}")
            print("-" * 30)
    else:
        print("Nenhuma MailBox encontrada. Criando uma de teste...")
        # Cria uma MailBox de teste
        test_mailbox = MailBox.objects.create(
            name="Teste MailBox",
            imap_host="imap.gmail.com",
            imap_port=993,
            username="teste@exemplo.com",
            password="senha-teste"
        )
        print(f"MailBox de teste criada com ID: {test_mailbox.id}")
    
    # Verifica emails existentes
    print("\n=== VERIFICACAO DE EMAILS ===")
    emails = EmailMessage.objects.all()
    print(f"Numero de emails encontrados: {emails.count()}")
    
    if emails.exists():
        print("Ultimos 5 emails:")
        for email in emails.order_by('-id')[:5]:
            print(f"ID: {email.id}")
            print(f"Subject: {getattr(email, 'subject', 'N/A')}")
            print(f"Status: {getattr(email, 'status', 'N/A')}")
            print(f"Created: {getattr(email, 'created_at', 'N/A')}")
            print("-" * 30)
    
    # Testa a funcao fetch_emails (simulacao)
    print("\n=== TESTE: FETCH_EMAILS ===")
    if mailboxes.exists():
        mailbox_id = mailboxes.first().id
        print(f"Testando fetch_emails com MailBox ID: {mailbox_id}")
        print("AVISO: Esta funcao tentara conectar ao servidor IMAP real!")
        print("Se nao tiver credenciais validas, pode falhar.")
        
        # Descomente a linha abaixo para testar realmente
        # result = fetch_emails(mailbox_id)
        # print(f"Resultado: {result} emails processados")
        
        print("Teste de fetch_emails pulado (descomente para testar)")
    else:
        print("Nenhuma MailBox disponivel para teste")
    
    # Testa a funcao process_email (simulacao)
    print("\n=== TESTE: PROCESS_EMAIL ===")
    if emails.exists():
        email_id = emails.first().id
        print(f"Testando process_email com Email ID: {email_id}")
        
        # Descomente a linha abaixo para testar realmente
        # process_email(email_id)
        # print("Processamento concluido")
        
        print("Teste de process_email pulado (descomente para testar)")
    else:
        print("Nenhum email disponivel para teste")
    
    # Testa processamento do email existente
    print("\n=== TESTE: PROCESSAMENTO DE EMAIL EXISTENTE ===")
    if emails.exists():
        test_email = emails.first()
        print(f"Usando email existente ID: {test_email.id}")
        print(f"Status atual: {test_email.status}")
        
        # Reseta o email para PENDING para testar novamente
        test_email.status = EmailStatus.PENDING
        test_email.processing_attempts = 0
        test_email.extracted_data = None
        test_email.save()
        print("Email resetado para PENDING")
        
        print(f"Subject: {test_email.subject}")
        print(f"Status: {test_email.status}")
        print(f"Body length: {len(test_email.body_text)} caracteres")
        
        # Testa processamento do email de teste
        print("\nTestando processamento do email de teste...")
        try:
            process_email(test_email.id)
            print("SUCESSO: Processamento concluido!")
            
            # Verifica o resultado
            test_email.refresh_from_db()
            print(f"Status final: {test_email.status}")
            print(f"Processing attempts: {test_email.processing_attempts}")
            
            if hasattr(test_email, 'extracted_data') and test_email.extracted_data:
                print("Dados extraidos:")
                for key, value in test_email.extracted_data.items():
                    print(f"  {key}: {value}")
            else:
                print("Nenhum dado extraido encontrado")
                
        except Exception as e:
            print(f"ERRO no processamento: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("Nenhum email disponivel para teste")
    
    print("\n" + "=" * 50)
    print("Teste concluido!")

if __name__ == "__main__":
    test_tasks_functionality()
