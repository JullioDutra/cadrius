#!/usr/bin/env python3
"""
Teste para validar o funcionamento do ai_wrapper.py com API real do OpenAI

"""

import os
import sys
import logging

# Adiciona o diretorio pai ao path para importar os modulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extraction.ai_wrapper import extract_fields_from_text, get_extraction_stats
from extraction.schemas import ServiceOrderSchema

# Configuracao de logging para ver os detalhes
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_real_api():
    """Testa a extracao com API real do OpenAI"""
    print("TESTE DO AI WRAPPER COM API REAL")
    print("=" * 50)
    
    # Mostra estatisticas
    print("\n=== ESTATISTICAS DO SISTEMA ===")
    stats = get_extraction_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    # Verifica se a API key esta configurada
    if not stats.get('api_key_available'):
        print("\nAVISO: OPENAI_API_KEY nao encontrada!")
        print("Configure a variavel de ambiente OPENAI_API_KEY para testar com API real.")
        print("Exemplo: export OPENAI_API_KEY='sua-chave-aqui'")
        return
    
    # Testa extracao com texto real
    print("\n=== TESTE: Extracao com API Real ===")
    
    sample_text = """
    Prezados,
    
    Gostaria de solicitar um novo servico para nossa empresa:
    
    Cliente: Tech Solutions Ltda
    Servico: Desenvolvimento de sistema de gestao de vendas
    Prioridade: Alta
    Prazo: 20 dias uteis
    Contato: (11) 99999-7777
    
    O sistema deve incluir:
    - Modulo de cadastro de clientes
    - Controle de estoque
    - Relatorios de vendas
    - Integracao com pagamentos
    
    Aguardo retorno.
    Atenciosamente,
    Maria Silva
    Gerente de TI
    """
    
    print("Texto de entrada:")
    print(sample_text)
    print("\n" + "-" * 50)
    
    result = extract_fields_from_text(
        text=sample_text,
        schema=ServiceOrderSchema,
        prompt_template="Extraia as informacoes de pedido de servico do texto abaixo. Seja preciso e detalhado:",
        examples=[]
    )
    
    if result:
        print("SUCESSO: Extracao funcionou!")
        print(f"Tipo do resultado: {type(result)}")
        print(f"Numero de campos extraidos: {len(result)}")
        print(f"Campos: {list(result.keys())}")
        print(f"Document type: {result.get('document_type', 'N/A')}")
        print(f"Confidence score: {result.get('confidence_score', 'N/A')}")
        print(f"Customer name: {result.get('customer_name', 'N/A')}")
        print(f"Service description: {result.get('service_description', 'N/A')}")
        print(f"Priority: {result.get('priority', 'N/A')}")
        print(f"Target SLA days: {result.get('target_sla_days', 'N/A')}")
        print(f"Contact phone: {result.get('contact_phone', 'N/A')}")
    else:
        print("FALHA: Extracao nao funcionou")
    
    print("\n" + "=" * 50)
    print("Teste concluido!")

if __name__ == "__main__":
    test_real_api()
