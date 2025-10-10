import os
import json
import logging
import time
from typing import Dict, Any, Optional, Union
from openai import OpenAI, RateLimitError, APIError, APIConnectionError, APITimeoutError
from pydantic import BaseModel, ValidationError

# Importa os schemas definidos por Juliano
from .schemas import ExtractedData, ServiceOrderSchema, SupportRequestSchema 

logger = logging.getLogger(__name__)

# Configuração do cliente OpenAI (lê a chave do settings.py via os.environ)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY não encontrada nas variáveis de ambiente. Usando modo MOCK.")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
AI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5")

# Número máximo de tentativas de re-prompt antes de falhar
MAX_RETRY_ATTEMPTS = 3
# Delay entre tentativas (em segundos)
RETRY_DELAY = 2


def extract_fields_from_text(
    text: str, 
    schema: type[BaseModel], 
    prompt_template: str, 
    examples: Optional[list] = None
) -> Optional[Dict[str, Any]]:
    """
    Extrai dados estruturados de um texto usando a API do OpenAI e valida com Pydantic.

    Args:
        text: O corpo do email a ser analisado.
        schema: O modelo Pydantic (ex: ServiceOrderSchema) para validação.
        prompt_template: O template de instrução para a IA.
        examples: Exemplos few-shot para guiar a extração (opcional).

    Returns:
        Um dicionário Python (JSON validado) ou None em caso de falha.
    """
    # Verificação inicial
    if not text or not text.strip():
        logger.error("Texto de entrada vazio ou inválido.")
        return None
    
    if not client:
        logger.warning("Cliente OpenAI não inicializado. Usando modo MOCK.")
        return mock_extract_fields_from_text(text, schema, prompt_template, examples)
    
    schema_json = schema.model_json_schema()
    
    # 1. Montagem do Prompt de Sistema (Instruções e Estrutura JSON)
    system_prompt = (
        "Você é um extrator de dados altamente eficiente. Sua única tarefa é analisar o texto "
        "fornecido e retornar os dados estritamente no formato JSON, conforme o schema abaixo. "
        "IMPORTANTE: Se não for possível preencher um campo obrigatório, use um valor padrão razoável. "
        "Para campos opcionais, use `null` se não encontrar informação.\n\n"
        f"SCHEMA JSON: {json.dumps(schema_json, indent=2)}"
    )

    # 2. Montagem da Mensagem do Usuário
    user_prompt = f"{prompt_template}\n\nTEXTO DE ENTRADA:\n---\n{text}"
    
    # Adiciona exemplos few-shot se fornecidos
    if examples:
        examples_text = "\n".join([f"Exemplo {i+1}: {ex}" for i, ex in enumerate(examples)])
        user_prompt = f"{examples_text}\n\n{user_prompt}"
    
    # Estratégia de Fallback com Retries
    for attempt in range(MAX_RETRY_ATTEMPTS):
        try:
            logger.info(f"Tentativa {attempt + 1}/{MAX_RETRY_ATTEMPTS}: Chamando API OpenAI...")
            
            # Delay progressivo entre tentativas
            if attempt > 0:
                delay = RETRY_DELAY * (2 ** (attempt - 1))  # Exponential backoff
                logger.info(f"Aguardando {delay}s antes da próxima tentativa...")
                time.sleep(delay)
            
            response = client.chat.completions.create(
                model=AI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                # Força a saída como JSON (necessita do modelo gpt-5 ou superior)
                response_format={"type": "json_object"},
                max_completion_tokens=2000,  # Limite razoável para respostas JSON (GPT-5)
                timeout=30  # Timeout de 30 segundos
            )

            raw_json_output = response.choices[0].message.content
            
            if not raw_json_output:
                logger.error(f"Tentativa {attempt + 1}: Resposta vazia da API OpenAI.")
                continue
            
            # Limpa a resposta (remove markdown code blocks se existirem)
            cleaned_output = raw_json_output.strip()
            if cleaned_output.startswith("```json"):
                cleaned_output = cleaned_output[7:]
            if cleaned_output.endswith("```"):
                cleaned_output = cleaned_output[:-3]
            cleaned_output = cleaned_output.strip()
            
            # 3. VALIDAÇÃO PYDANTIC (CRÍTICO)
            try:
                validated_model = schema.model_validate_json(cleaned_output)
                logger.info(f"Tentativa {attempt + 1}: Extração bem-sucedida!")
                return validated_model.model_dump()
            except ValidationError as e:
                logger.error(f"Tentativa {attempt + 1}: Falha na validação Pydantic. Erro: {e}")
                # Constrói mensagem de erro detalhada para a próxima tentativa
                error_details = []
                for error in e.errors():
                    field = error.get('loc', ['unknown'])[-1]
                    msg = error.get('msg', 'Erro desconhecido')
                    error_details.append(f"- Campo '{field}': {msg}")
                
                error_message = f"O JSON retornado falhou na validação. Erros encontrados:\n" + "\n".join(error_details)
                user_prompt += f"\n\nCORREÇÃO NECESSÁRIA:\n{error_message}\n\nPor favor, corrija o JSON conforme o schema fornecido."
                continue

        except json.JSONDecodeError as e:
            logger.error(f"Tentativa {attempt + 1}: Resposta da IA não é um JSON válido. Erro: {e}")
            user_prompt += f"\n\nERRO DE JSON: A saída anterior não foi um JSON válido. Erro: {e}\nPor favor, retorne APENAS um JSON válido conforme o schema."
            
        except RateLimitError as e:
            logger.warning(f"Tentativa {attempt + 1}: Rate limit atingido. Aguardando... Erro: {e}")
            if attempt < MAX_RETRY_ATTEMPTS - 1:
                time.sleep(60)  # Aguarda 1 minuto para rate limit
            continue
            
        except APITimeoutError as e:
            logger.warning(f"Tentativa {attempt + 1}: Timeout na API OpenAI. Erro: {e}")
            continue
            
        except APIConnectionError as e:
            logger.warning(f"Tentativa {attempt + 1}: Erro de conexão com API OpenAI. Erro: {e}")
            continue
            
        except APIError as e:
            logger.error(f"Tentativa {attempt + 1}: Erro da API OpenAI. Código: {e.code}, Tipo: {e.type}, Erro: {e}")
            if e.code == 'invalid_api_key':
                logger.critical("Chave API inválida. Interrompendo tentativas.")
                break
            continue
            
        except Exception as e:
            logger.critical(f"Tentativa {attempt + 1}: Erro inesperado na comunicação com API OpenAI: {e}")
            if attempt == MAX_RETRY_ATTEMPTS - 1:
                break
            continue

    # 4. FALLBACK FINAL: Marcação para Revisão Humana
    logger.error(f"Extração falhou após {MAX_RETRY_ATTEMPTS} tentativas. Retornando None.")
    return None

# --------------------------------------------------------------------------------
# MOCK DE TESTE (A ser usado por Juliano para testes unitários em CI)
# --------------------------------------------------------------------------------

def mock_extract_fields_from_text(
    text: str, 
    schema: type[BaseModel], 
    prompt_template: str = "", 
    examples: Optional[list] = None
) -> Optional[Dict[str, Any]]:
    """
    Simula a extração de IA para testes em ambientes onde a chave API não está disponível.
    """
    logger.warning("Usando MOCK de extração de IA. Apenas para testes unitários.")
    
    # Simula um pequeno delay para parecer mais realista
    time.sleep(0.5)
    
    try:
        if schema == ServiceOrderSchema:
            return ServiceOrderSchema(
                document_type='SERVICE_ORDER',
                confidence_score=95,
                customer_name="Cliente Mock Teste LTDA",
                service_description="Implementação do módulo de IA conforme specs.",
                priority='HIGH',
                target_sla_days=7,
                contact_phone="9999-8888"
            ).model_dump()
        elif schema == SupportRequestSchema:
            return SupportRequestSchema(
                document_type='SUPPORT_REQUEST',
                confidence_score=90,
                system_affected="Sistema de Email",
                issue_summary="Problema na extração de dados",
                is_critical=False,
                error_code="ERR_001",
                requester_email="teste@exemplo.com"
            ).model_dump()
        else:
            # Fallback genérico para outros schemas
            return {
                "document_type": "OTHER",
                "confidence_score": 85,
                "extracted_text": text[:100] + "..." if len(text) > 100 else text
            }
    except Exception as e:
        logger.error(f"Erro no mock de extração: {e}")
        return None


def get_extraction_stats() -> Dict[str, Any]:
    """
    Retorna estatísticas de uso da extração de IA.
    Útil para monitoramento e debugging.
    """
    return {
        "client_initialized": client is not None,
        "api_key_available": OPENAI_API_KEY is not None,
        "model": AI_MODEL,
        "max_retry_attempts": MAX_RETRY_ATTEMPTS,
        "retry_delay": RETRY_DELAY
    }


def validate_extraction_result(result: Optional[Dict[str, Any]], schema: type[BaseModel]) -> bool:
    """
    Valida se o resultado da extração está correto conforme o schema.
    Útil para testes e validação pós-processamento.
    """
    if result is None:
        return False
    
    try:
        schema.model_validate(result)
        return True
    except ValidationError:
        return False
