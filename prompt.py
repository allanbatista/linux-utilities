#!/usr/bin/env python3
"""
CLI to concatenate file contents and send to OpenRouter.

Configuration via `~/.ab/config.json` (optional).

Example `~/.ab/config.json`:
{
  "global": {
    "language": "en",
    "api_base": "https://openrouter.ai/api/v1",
    "api_key_env": "OPENROUTER_API_KEY",
    "timeout_seconds": 300
  },
  "models": {
    "default": "nvidia/nemotron-3-nano-30b-a3b:free"
  }
}

Flag `--set-default-model <model>` to **persist** the default model.
"""
import argparse
import os
import pathlib
import json
import requests
import pyperclip
import datetime
import sys
import subprocess
from typing import Optional, Tuple, Dict, Any, List

from binaryornot.check import is_binary
import pathspec

VERBOSE = True

def pp(*args, **kwargs):
    if VERBOSE:
        print(*args, **kwargs)

# =========================
# Utilitários e Persistência
# =========================

def load_config() -> Dict[str, Any]:
    """Load config from ~/.ab/config.json using centralized config module."""
    try:
        # Add script directory to path for imports
        script_dir = pathlib.Path(__file__).parent
        sys.path.insert(0, str(script_dir))
        from lib.ab_config import get_config

        config = get_config()
        # Return in legacy format for compatibility
        return {
            "model": config.get("models.default"),
            "api_base": config.get("global.api_base"),
            "api_key_env": config.get("global.api_key_env"),
            "request": {
                "timeout_seconds": config.get("global.timeout_seconds", 300)
            }
        }
    except Exception as e:
        pp(f"Warning: could not read config: {e}")
    return {}


def persist_default_model(new_model: str) -> bool:
    """
    Update default model in ~/.ab/config.json (models.default key),
    preserving other fields. Creates the file if it doesn't exist.
    """
    try:
        script_dir = pathlib.Path(__file__).parent
        sys.path.insert(0, str(script_dir))
        from lib.ab_config import get_config

        config = get_config()
        config.set("models.default", new_model)
        return True
    except Exception as e:
        pp(f"Error persisting default model: {e}")
        return False


# =========================
# Providers
# =========================

def build_specialist_prefix(specialist: Optional[str]) -> str:
    specialist_prompts = {
        'dev': 'Aja como um programador sênior especialista em desenvolvimento de software, com mais de 20 anos de experiência. Suas respostas devem ser claras, eficientes, bem-estruturadas e seguir as melhores práticas do mercado. Pense passo a passo.',
        'rm': 'Aja como um analista de Retail Media sênior, especialista em estratégias de publicidade digital para e-commerce e marketplaces. Seu conhecimento abrange plataformas como Amazon Ads, Mercado Ads e Criteo. Suas respostas devem ser analíticas, estratégicas e baseadas em dados.'
    }
    return specialist_prompts.get(specialist or "", "")


def send_to_openrouter(prompt: str, context: str, lang: str, specialist: Optional[str],
                        model_name: str, timeout_s: int, max_completion_tokens: int = 256,
                        api_key_env: str = "OPENROUTER_API_KEY",
                        api_base: str = "https://openrouter.ai/api/v1") -> Optional[Dict[str, Any]]:
    """
    Envia o prompt e o contexto para a API do OpenRouter (compatível com OpenAI).
    """
    api_key = os.getenv(api_key_env)
    if not api_key:
        pp(f"Erro: A variável de ambiente {api_key_env} não está definida.")
        return None

    # Construção do prompt completo
    parts = []
    specialist_prefix = build_specialist_prefix(specialist)
    if specialist_prefix:
        parts.append(specialist_prefix)

    parts.append(prompt)

    if context.strip():
        parts.append("\n--- CONTEXTO DOS ARQUIVOS ---\n" + context)

    parts.append(f"--- INSTRUÇÃO DE SAÍDA ---\nResponda estritamente na linguagem: {lang}.")

    full_prompt = "\n\n".join(parts)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    url = f"{api_base.rstrip('/')}/chat/completions"

    messages = [{"role": "user", "content": full_prompt}]
    if specialist_prefix:
        messages.insert(0, {"role": "system", "content": specialist_prefix})

    payload = {
        "model": model_name,
        "messages": messages,
    }

    if max_completion_tokens > 0:
        payload["max_tokens"] = max_completion_tokens

    try:
        pp(f"Enviando requisição para OpenRouter ({model_name})...")
        response = requests.post(url, headers=headers, json=payload, timeout=timeout_s)
        response.raise_for_status()
        data = response.json()

        text_response = data['choices'][0]['message']['content']
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", "N/A")
        response_tokens = usage.get("completion_tokens", "N/A")

        return {
            "provider": "openrouter",
            "model": model_name,
            "text": text_response,
            "prompt_tokens": prompt_tokens,
            "response_tokens": response_tokens,
            "full_prompt": full_prompt,
        }

    except requests.exceptions.RequestException as e:
        pp(f"Erro de rede ou HTTP ao chamar OpenRouter: {e}")
        if getattr(e, 'response', None) is not None:
            try:
                pp(f"Detalhes do erro: {e.response.text}")
            except Exception:
                pass
        return None
    except (KeyError, IndexError) as e:
        pp(f"Erro ao extrair conteúdo da resposta: {e}")
        try:
            pp("Estrutura da resposta recebida:", response.json())
        except Exception:
            pass
        return None
    except Exception as e:
        pp(f"Erro inesperado: {e}")
        return None


# =========================
# Histórico e Persistência
# =========================

def save_to_history(full_prompt: str, response_text: str, result: Dict[str, Any],
                     files_info: Dict[str, Any], args: argparse.Namespace) -> None:
    """
    Save full interaction history with LLM to ~/.ab/history/

    Information saved:
    - Request timestamp
    - Provider and model used
    - Full prompt and response
    - Token metrics (prompt, response, total)
    - Processed files information
    - Configuration used (specialist, language, etc)
    - Prompt hash to avoid duplicates
    """
    try:
        import hashlib

        # History directory
        history_dir = pathlib.Path.home() / ".ab" / "history"
        history_dir.mkdir(parents=True, exist_ok=True)
        
        # Nome do arquivo baseado em timestamp
        timestamp = datetime.datetime.now()
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
        
        # Hash do prompt para referência única
        prompt_hash = hashlib.md5(full_prompt.encode('utf-8')).hexdigest()[:8]
        
        # Estrutura completa de dados
        history_entry = {
            "metadata": {
                "timestamp": timestamp.isoformat(),
                "timestamp_formatted": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "prompt_hash": prompt_hash,
                "session_id": f"{timestamp_str}_{prompt_hash}"
            },
            "provider_info": {
                "provider": result.get('provider', 'unknown'),
                "model": result.get('model', 'unknown'),
                "api_version": result.get('api_version', 'N/A')
            },
            "tokens": {
                "prompt_tokens": result.get('prompt_tokens', 'N/A'),
                "response_tokens": result.get('response_tokens', 'N/A'),
                "total_tokens": (
                    result.get('prompt_tokens', 0) + result.get('response_tokens', 0)
                    if isinstance(result.get('prompt_tokens'), int) and isinstance(result.get('response_tokens'), int)
                    else 'N/A'
                ),
                "estimated_cost_usd": calculate_estimated_cost(
                    result.get('model', ''),
                    result.get('prompt_tokens', 0),
                    result.get('response_tokens', 0)
                )
            },
            "files_info": {
                "processed_count": files_info.get('processed', 0),
                "error_count": files_info.get('errors', 0),
                "skipped_count": files_info.get('skipped', 0),
                "total_words": files_info.get('words', 0),
                "total_estimated_tokens": files_info.get('tokens', 0),
                "file_list": files_info.get('file_list', [])
            },
            "configuration": {
                "specialist": args.specialist if hasattr(args, 'specialist') else None,
                "language": args.lang if hasattr(args, 'lang') else 'pt-br',
                "max_tokens": args.max_tokens if hasattr(args, 'max_tokens') else None,
                "max_tokens_doc": args.max_tokens_doc if hasattr(args, 'max_tokens_doc') else None,
                "max_completion_tokens": 0 if getattr(args, 'unlimited', False) else (args.max_completion_tokens if hasattr(args, 'max_completion_tokens') else 16000),
                "path_format": (
                    'relative' if args.relative_paths else
                    'name_only' if args.filename_only else
                    'full'
                ) if hasattr(args, 'relative_paths') else 'full'
            },
            "content": {
                "prompt": {
                    "full": full_prompt,
                    "length_chars": len(full_prompt),
                    "length_words": len(full_prompt.split())
                },
                "response": {
                    "full": response_text,
                    "length_chars": len(response_text),
                    "length_words": len(response_text.split()),
                    "preview": response_text[:500] + "..." if len(response_text) > 500 else response_text
                }
            },
            "statistics": {
                "prompt_to_response_ratio": round(len(response_text) / len(full_prompt), 2) if full_prompt else 0,
                "avg_response_word_length": round(len(response_text) / max(len(response_text.split()), 1), 2),
                "response_lines": response_text.count('\n') + 1
            }
        }
        
        # Salvar arquivo individual
        history_file = history_dir / f"history_{timestamp_str}_{prompt_hash}.json"
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history_entry, f, indent=2, ensure_ascii=False)
        
        # Atualizar índice mestre
        update_history_index(history_dir, history_entry)
        
        # # Limpar históricos antigos (manter últimos 100)
        # cleanup_old_history(history_dir, keep_last=100)
        
        pp(f"💾 Histórico salvo: {history_file}")
        
    except Exception as e:
        pp(f"⚠️  Aviso: Não foi possível salvar o histórico: {e}")


def calculate_estimated_cost(model: str, prompt_tokens: int, response_tokens: int) -> float:
    """
    Calcula o custo estimado baseado no modelo e tokens utilizados.
    Valores aproximados (podem variar).
    """
    if not isinstance(prompt_tokens, int) or not isinstance(response_tokens, int):
        return 0.0
    
    # Preços aproximados por 1M tokens (USD) - atualizar conforme necessário
    pricing = {
        # OpenAI
        'gpt-4o': {'prompt': 2.50, 'response': 10.00},
        'gpt-4o-mini': {'prompt': 0.15, 'response': 0.60},
        'gpt-4-turbo': {'prompt': 10.00, 'response': 30.00},
        'gpt-4': {'prompt': 30.00, 'response': 60.00},
        'gpt-3.5-turbo': {'prompt': 0.50, 'response': 1.50},
        
        # Google Gemini (estimativas)
        'gemini-1.5-pro': {'prompt': 3.50, 'response': 10.50},
        'gemini-1.5-flash': {'prompt': 0.075, 'response': 0.30},
        'gemini-pro': {'prompt': 0.50, 'response': 1.50},
    }
    
    # Encontrar preço do modelo
    model_lower = model.lower()
    price_info = None
    
    for model_key, prices in pricing.items():
        if model_key in model_lower:
            price_info = prices
            break
    
    if not price_info:
        return 0.0
    
    # Calcular custo
    prompt_cost = (prompt_tokens / 1_000_000) * price_info['prompt']
    response_cost = (response_tokens / 1_000_000) * price_info['response']
    
    return round(prompt_cost + response_cost, 6)


def update_history_index(history_dir: pathlib.Path, entry: Dict[str, Any]) -> None:
    """
    Atualiza o arquivo índice mestre com resumo das interações.
    """
    index_file = history_dir / "index.json"
    
    try:
        if index_file.exists():
            with open(index_file, 'r', encoding='utf-8') as f:
                index = json.load(f)
        else:
            index = {
                "created_at": datetime.datetime.now().isoformat(),
                "total_interactions": 0,
                "total_tokens_used": 0,
                "total_estimated_cost": 0.0,
                "interactions": []
            }
        
        # Adicionar resumo da interação
        summary = {
            "session_id": entry['metadata']['session_id'],
            "timestamp": entry['metadata']['timestamp'],
            "provider": entry['provider_info']['provider'],
            "model": entry['provider_info']['model'],
            "tokens": entry['tokens'].get('total_tokens', 'N/A'),
            "cost": entry['tokens'].get('estimated_cost_usd', 0.0),
            "files_processed": entry['files_info']['processed_count'],
            "response_preview": entry['content']['response']['preview']
        }
        
        index['interactions'].insert(0, summary)  # Mais recente primeiro
        index['total_interactions'] = len(index['interactions'])
        
        # Atualizar totais
        if isinstance(entry['tokens'].get('total_tokens'), int):
            index['total_tokens_used'] += entry['tokens']['total_tokens']
        
        if isinstance(entry['tokens'].get('estimated_cost_usd'), (int, float)):
            index['total_estimated_cost'] += entry['tokens']['estimated_cost_usd']
            index['total_estimated_cost'] = round(index['total_estimated_cost'], 6)
        
        # Salvar índice
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        pp(f"⚠️  Aviso: Não foi possível atualizar o índice: {e}")


def cleanup_old_history(history_dir: pathlib.Path, keep_last: int = 100) -> None:
    """
    Remove arquivos de histórico mais antigos, mantendo apenas os últimos N.
    """
    try:
        history_files = sorted(
            history_dir.glob("history_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        if len(history_files) > keep_last:
            for old_file in history_files[keep_last:]:
                old_file.unlink()
                
    except Exception as e:
        # Não crítico, apenas log silencioso
        pass


# =========================
# Detecção de Binários
# =========================

def is_binary_file(file_path: pathlib.Path) -> bool:
    """
    Detecta se um arquivo é binário usando a biblioteca binaryornot.

    Args:
        file_path: Caminho do arquivo a verificar.

    Returns:
        True se o arquivo é binário, False se é texto.
    """
    try:
        return is_binary(str(file_path))
    except Exception:
        return True  # Se não conseguir ler, assume binário


# =========================
# Suporte a .aiignore
# =========================

def find_git_root(start_path: pathlib.Path) -> Optional[pathlib.Path]:
    """
    Encontra a raiz do repositório git a partir do caminho inicial.

    Args:
        start_path: Caminho inicial para busca.

    Returns:
        Caminho da raiz do git ou None se não estiver em um repositório.
    """
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            capture_output=True, text=True, cwd=str(start_path)
        )
        if result.returncode == 0:
            return pathlib.Path(result.stdout.strip())
    except Exception:
        pass
    return None


def find_aiignore_files(start_path: pathlib.Path) -> List[pathlib.Path]:
    """
    Procura arquivos .aiignore do diretório inicial até a raiz do git.

    Args:
        start_path: Caminho inicial para busca.

    Returns:
        Lista de caminhos de arquivos .aiignore encontrados (do mais específico ao mais geral).
    """
    aiignore_files = []
    current = start_path.resolve()
    git_root = find_git_root(current)

    while current != current.parent:
        aiignore_path = current / '.aiignore'
        if aiignore_path.exists() and aiignore_path.is_file():
            aiignore_files.append(aiignore_path)

        # Para na raiz do git se encontrada
        if git_root and current == git_root:
            break

        current = current.parent

    return aiignore_files


def load_aiignore_spec(aiignore_files: List[pathlib.Path]) -> Optional[pathspec.GitIgnoreSpec]:
    """
    Carrega e combina padrões de múltiplos arquivos .aiignore.

    Args:
        aiignore_files: Lista de caminhos de .aiignore (do mais específico ao mais geral).

    Returns:
        Spec combinado ou None se não houver padrões.
    """
    all_patterns = []

    # Processa do mais geral (raiz) para o mais específico
    for aiignore_path in reversed(aiignore_files):
        try:
            with open(aiignore_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            all_patterns.extend(lines)
        except Exception as e:
            pp(f"Aviso: Erro ao ler {aiignore_path}: {e}")

    if not all_patterns:
        return None

    return pathspec.GitIgnoreSpec.from_lines(all_patterns)


def should_ignore_path(
    file_path: pathlib.Path,
    spec: Optional[pathspec.GitIgnoreSpec],
    base_path: pathlib.Path
) -> bool:
    """
    Verifica se um arquivo deve ser ignorado com base nos padrões .aiignore.

    Args:
        file_path: Caminho absoluto do arquivo.
        spec: Spec compilado do GitIgnore (ou None).
        base_path: Caminho base para cálculo de caminho relativo.

    Returns:
        True se o arquivo deve ser ignorado.
    """
    if spec is None:
        return False

    try:
        rel_path = file_path.relative_to(base_path)
        return spec.match_file(str(rel_path))
    except ValueError:
        # file_path não é relativo a base_path
        return spec.match_file(str(file_path))


# =========================
# Processamento de Arquivos
# =========================

def process_file(file_path: pathlib.Path, path_format: str, max_tokens_doc: int) -> Tuple[str, int, int]:
    """
    Lê o conteúdo de um arquivo, formata o cabeçalho e trunca se necessário com base em tokens.

    Args:
        file_path: O caminho do arquivo a ser processado.
        path_format: Como o caminho deve ser formatado ('full', 'relative', 'name_only').
        max_tokens_doc: O número máximo de tokens estimados para este arquivo.

    Returns:
        Uma tupla contendo o conteúdo formatado, a contagem de palavras e os tokens estimados.
    """
    try:
        display_path = ""
        if path_format == 'name_only':
            display_path = file_path.name
        elif path_format == 'relative':
            display_path = os.path.relpath(file_path.resolve(), pathlib.Path.cwd())
        else: # 'full'
            display_path = str(file_path.resolve())

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        original_tokens = len(content) // 4
        warning_message = ""

        if original_tokens > max_tokens_doc:
            max_chars = max_tokens_doc * 4
            content = content[:max_chars]
            warning_message = (
                f"// warning_content_truncated=\"true\" "
                f"original_token_count=\"{original_tokens}\" "
                f"new_token_count=\"{max_tokens_doc}\"\n"
            )
            pp(f"  -> Aviso: O arquivo '{display_path}' foi truncado para ~{max_tokens_doc} tokens.")

        word_count = len(content.split())
        estimated_tokens = len(content) // 4
        formatted_content = f"// filename=\"{display_path}\"\n{warning_message}{content}\n"
        
        return formatted_content, word_count, estimated_tokens
    except Exception as e:
        error_message = f"// error_processing_file=\"{file_path.resolve()}\"\n// Error: {e}\n"
        return error_message, 0, 0


# =========================
# Configuração Efetiva
# =========================

def resolve_settings(args, config: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve model/timeout/api_base/api_key_env a partir de args + config."""
    # Model precedence: CLI > config > default
    model = args.model or config.get("model") or "nvidia/nemotron-3-nano-30b-a3b:free"

    # API key env var name
    api_key_env = config.get("api_key_env") or "OPENROUTER_API_KEY"

    # API base
    api_base = config.get("api_base") or "https://openrouter.ai/api/v1"

    # Timeout
    timeout_s = int(config.get("request", {}).get("timeout_seconds", 300))

    return {
        "model": model,
        "api_key_env": api_key_env,
        "api_base": api_base,
        "timeout_s": timeout_s,
    }


# =========================
# Main
# =========================

def main():
    """Função principal que orquestra a execução do script."""
    parser = argparse.ArgumentParser(
        description=(
            "Concatena o conteúdo de arquivos de texto (ignora binários) e "
            "opcionalmente envia para a API do OpenRouter.\n"
            "Use .aiignore para excluir arquivos (sintaxe igual ao .gitignore)."
        ),
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "paths",
        metavar="PATH",
        type=pathlib.Path,
        nargs='*',
        help="Uma lista de arquivos e/ou diretórios para processar."
    )
    parser.add_argument(
        "-p", "--prompt",
        type=str,
        help="Um prompt opcional para enviar à API. Use '-' para ler do stdin."
    )
    parser.add_argument(
        '--lang',
        type=str,
        default='en',
        help='Output language. Default: en'
    )
    parser.add_argument(
        '-n', '--max-tokens',
        type=int,
        default=900_000,
        help='Tamanho máximo em tokens estimados para o contexto total. Padrão: 900000'
    )
    parser.add_argument(
        '-nn', '--max-tokens-doc',
        type=int,
        default=250_000,
        help='Tamanho máximo em tokens estimados para cada arquivo individual. Padrão: 250000'
    )
    parser.add_argument(
        '-s', '--specialist',
        type=str,
        choices=['dev', 'rm'],
        help=(
            "Define uma persona especialista:\n"
            "'dev' para Programador Sênior\n"
            "'rm'  para Analista de Retail Media Sênior."
        )
    )
    parser.add_argument(
        '--model',
        type=str,
        help='Nome do modelo OpenRouter a ser usado. Ex: nvidia/nemotron-3-nano-30b-a3b:free'
    )
    parser.add_argument(
        '-m', '--max-completion-tokens',
        type=int,
        default=16000,
        help='Número máximo de tokens para a resposta do modelo. Padrão: 16000'
    )
    parser.add_argument(
        '-u', '--unlimited',
        action='store_true',
        help='Remove o limite de tokens da resposta (não envia max_tokens para a API)'
    )
    parser.add_argument(
        '--set-default-model',
        type=str,
        help='Define e persiste o modelo padrão (top-level "model") em ~/.prompt/config.json e encerra, se nenhum outro argumento for passado.'
    )
    parser.add_argument(
        '--only-output',
        action='store_true',
        help="retorna apenas o resultado do modelo"
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help="formata o resulto json"
    )

    path_options = parser.add_mutually_exclusive_group()
    path_options.add_argument(
        "--relative-paths",
        action="store_true",
        help="Exibe caminhos relativos em vez de caminhos absolutos."
    )
    path_options.add_argument(
        "--filename-only",
        action="store_true",
        help="Exibe apenas o nome do arquivo em vez do caminho completo."
    )
    

    # Se nenhum argumento for passado, exibe a ajuda
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    # Se prompt for '-', lê do stdin
    if args.prompt == '-':
        args.prompt = sys.stdin.read()

    global VERBOSE
    VERBOSE = not args.only_output

    # Atualiza modelo default, se solicitado
    if args.set_default_model:
        if persist_default_model(args.set_default_model):
            pp(f"✅ Modelo default atualizado para: {args.set_default_model} em ~/.prompt/config.json")
        else:
            pp("Erro ao atualizar o modelo default.")
        # Se apenas setou o default e não forneceu prompt nem caminhos, encerra.
        if not args.prompt and len(args.paths) == 0:
            return

    # Carrega configurações
    config = load_config()
    settings = resolve_settings(args, config)

    path_format_option = 'full'
    if args.relative_paths:
        path_format_option = 'relative'
    elif args.filename_only:
        path_format_option = 'name_only'

    # Carrega padrões .aiignore
    aiignore_files = find_aiignore_files(pathlib.Path.cwd())
    aiignore_spec = load_aiignore_spec(aiignore_files)
    if aiignore_files:
        pp(f"Carregado .aiignore de: {', '.join(str(f) for f in aiignore_files)}")

    all_files_content = []
    total_word_count = 0
    total_estimated_tokens = 0
    files_processed_count = 0
    files_error_count = 0
    files_skipped_count = 0

    for path_arg in args.paths:
        if not path_arg.exists():
            pp(f"Aviso: O caminho '{path_arg}' não existe. Pulando.")
            continue

        base_path = path_arg.resolve() if path_arg.is_dir() else path_arg.parent.resolve()

        if path_arg.is_file():
            # Verifica .aiignore
            if should_ignore_path(path_arg.resolve(), aiignore_spec, base_path):
                pp(f"Ignorado por .aiignore: {path_arg}")
                files_skipped_count += 1
                continue
            # Verifica se é binário
            if is_binary_file(path_arg):
                pp(f"Ignorado (binário): {path_arg}")
                files_skipped_count += 1
                continue
            # Processa arquivo de texto
            content, word_count, estimated_tokens = process_file(path_arg, path_format_option, args.max_tokens_doc)
            pp(f"Processando arquivo: {path_arg.resolve()} ({word_count} palavras, ~{estimated_tokens} tokens)")
            if content.startswith("// error_processing_file"):
                files_error_count += 1
            else:
                files_processed_count += 1
                total_word_count += word_count
                total_estimated_tokens += estimated_tokens
            all_files_content.append(content)

        elif path_arg.is_dir():
            pp(f"Processando diretório: {path_arg.resolve()}")
            for child_path in path_arg.rglob('*'):
                if child_path.is_file():
                    # Verifica .aiignore
                    if should_ignore_path(child_path.resolve(), aiignore_spec, base_path):
                        files_skipped_count += 1
                        continue
                    # Verifica se é binário
                    if is_binary_file(child_path):
                        files_skipped_count += 1
                        continue
                    # Processa arquivo de texto
                    content, word_count, estimated_tokens = process_file(child_path, path_format_option, args.max_tokens_doc)
                    pp(f"  -> Processando: {child_path.relative_to(path_arg)} ({word_count} palavras, ~{estimated_tokens} tokens)")
                    if content.startswith("// error_processing_file"):
                        files_error_count += 1
                    else:
                        files_processed_count += 1
                        total_word_count += word_count
                        total_estimated_tokens += estimated_tokens
                    all_files_content.append(content)
        else:
            pp(f"Aviso: O caminho '{path_arg}' não é um arquivo nem um diretório. Pulando.")

    final_text = "".join(all_files_content)

    # Caso nenhum arquivo tenha sido processado
    if not final_text and not args.prompt:
        pp("\nNenhum arquivo válido foi encontrado ou processado.")
        if files_skipped_count > 0:
            pp(f"{files_skipped_count} arquivo(s) foram ignorados (binários ou .aiignore).")
        return

    original_total_tokens = len(final_text) // 4
    if args.max_tokens and original_total_tokens > args.max_tokens:
        pp(f"\nAviso: O contexto final com ~{original_total_tokens} tokens excedeu o limite de {args.max_tokens}. Truncando...")
        max_chars = args.max_tokens * 4
        final_text = final_text[:max_chars]
        pp(f"Novo total de tokens estimados no contexto: ~{len(final_text) // 4}")

    # Realiza a chamada ao OpenRouter caso exista prompt
    if args.prompt:
        model = settings["model"]
        timeout_s = settings["timeout_s"]
        api_key_env = settings["api_key_env"]
        api_base = settings["api_base"]

        max_tokens = 0 if args.unlimited else args.max_completion_tokens
        result = send_to_openrouter(
            args.prompt, final_text, args.lang, args.specialist,
            model, timeout_s, max_tokens,
            api_key_env=api_key_env, api_base=api_base
        )

        if result:
            # print(json.dumps(result, indent=4))
            response_text = result['text']
            

            if VERBOSE:
                pp("\n--- INFORMAÇÕES DA REQUISIÇÃO ---")
                pp(f"Provider Utilizado: {result['provider']}")
                pp(f"Modelo Utilizado: {result['model']}")
                pp(f"Arquivos Processados: {files_processed_count} ({total_word_count} palavras, ~{total_estimated_tokens} tokens) | Erros: {files_error_count} | Ignorados: {files_skipped_count}")
                pp(f"Tokens Enviados (API): {result['prompt_tokens']}")
                pp(f"Tokens Recebidos (API): {result['response_tokens']}")
                pp("---------------------------------")
                
                pp("\n--- RESPOSTA DO MODELO ---\n")
                pp(response_text)
                pp("\n--------------------------\n")
            else:
                text = response_text.strip()

                if args.json:
                    if text.startswith('```json'):
                        text = text.replace('```json', '').replace('```', '')

                    try:
                        text = json.dumps(json.loads(text), indent=4)
                    except:
                        pass

                print(text)
                
            try:
                pyperclip.copy(response_text)
                pp("✅ Resposta copiada para a área de transferência!")
            except pyperclip.PyperclipException as e:
                pp(f"Erro: Não foi possível copiar para a área de transferência. {e}")

            # Preparar informações dos arquivos processados
            files_info = {
                'processed': files_processed_count,
                'errors': files_error_count,
                'skipped': files_skipped_count,
                'words': total_word_count,
                'tokens': total_estimated_tokens,
                'file_list': [str(p) for p in args.paths]
            }
            
            save_to_history(result['full_prompt'], response_text, result, files_info, args)
        return

    # Se não houver prompt, mas houver conteúdo de arquivo, copie para o clipboard
    if final_text:
        try:
            pyperclip.copy(final_text)
            pp(f"\nProcessado(s) {files_processed_count} arquivo(s) com sucesso ({total_word_count} palavras, ~{total_estimated_tokens} tokens no total).")
            if files_skipped_count > 0:
                 pp(f"{files_skipped_count} arquivo(s) foram ignorados (binários ou .aiignore).")
            if files_error_count > 0:
                pp(f"Encontrados erros em {files_error_count} arquivo(s).")
            pp("✅ O conteúdo combinado foi copiado para a sua área de transferência!")
        except pyperclip.PyperclipException as e:
            pp(f"\nErro: Não foi possível copiar para a área de transferência. {e}")
            pp("\nAqui está a saída combinada:\n")
            pp("--------------------------------------------------")
            pp(final_text)
            pp("--------------------------------------------------")


if __name__ == "__main__":
    main()