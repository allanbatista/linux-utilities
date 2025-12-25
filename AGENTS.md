# Repository Guidelines

## Project Structure & Module Organization

O repositório contém utilitários CLI unificados sob o comando `ab`. Estrutura atual:

```
linux-utilities/
├── ab                    # Comando principal (dispatcher)
├── ab.bash-completion    # Autocompletion para bash
├── auto-commit           # Gera mensagens de commit via LLM
├── pr-description        # Gera título/descrição de PR via LLM
├── prompt                # Wrapper bash para prompt.py
├── prompt.py             # CLI para enviar contexto ao OpenRouter
├── passgenerator         # Gerador de senhas seguras
└── requirements.txt      # Dependências Python
```

Configurações do usuário ficam em `~/.prompt/config.json`. Histórico de chamadas em `~/.prompt/history/`.

## Comandos Disponíveis

### ab (comando unificado)
```bash
ab <subcomando> [opções]

# Subcomandos:
ab auto-commit      # Gera mensagem de commit via LLM
ab pr-description   # Gera título/descrição de PR via LLM
ab prompt           # Envia contexto para LLM (OpenRouter)
ab passgenerator    # Gerador de senhas seguras
ab help             # Mostra ajuda
```

### auto-commit
Gera mensagens de commit automaticamente analisando o diff staged.
```bash
ab auto-commit              # Gera mensagem e confirma
ab auto-commit -a           # Adiciona todos os arquivos (git add -A)
ab auto-commit -y           # Pula confirmação
ab auto-commit -a -y        # Adiciona tudo e commita sem confirmar
```

### pr-description
Gera título e descrição de PR analisando commits e diff relativos à branch base.
```bash
ab pr-description              # Gera título e descrição
ab pr-description -c           # Gera e cria PR via gh CLI
ab pr-description -c -d        # Cria como draft
ab pr-description -b develop   # Especifica branch base
ab pr-description -c -y        # Cria PR sem confirmar
```

### prompt
Envia contexto de arquivos para o OpenRouter e retorna resposta do LLM.
```bash
ab prompt -p "pergunta"                    # Envia prompt simples
ab prompt arquivo.py -p "explique"         # Envia arquivo como contexto
ab prompt src/ -p "resuma o código"        # Envia diretório inteiro
ab prompt --model "openai/gpt-4o" -p "oi"  # Especifica modelo
ab prompt --only-output -p "oi"            # Retorna apenas resposta
ab prompt --set-default-model "modelo"     # Define modelo padrão
```

### passgenerator
Gera senhas seguras com validações.
```bash
ab passgenerator 16                    # Senha de 16 caracteres
ab passgenerator 20 --min-digits 4     # Mínimo 4 dígitos
ab passgenerator 12 --no-punct         # Sem pontuação
```

## Instalação

```bash
# Clonar repositório
git clone <repo-url>
cd linux-utilities

# Instalar dependências Python
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Adicionar ao PATH (opcional)
sudo ln -s $(pwd)/ab /usr/local/bin/ab

# Ativar autocompletion
mkdir -p ~/.local/share/bash-completion/completions
ln -s $(pwd)/ab.bash-completion ~/.local/share/bash-completion/completions/ab
```

## Configuração

### OpenRouter API Key
```bash
export OPENROUTER_API_KEY="sua-chave-aqui"
```

### Config persistente (~/.prompt/config.json)
```json
{
  "model": "nvidia/nemotron-3-nano-30b-a3b:free",
  "api_base": "https://openrouter.ai/api/v1",
  "api_key_env": "OPENROUTER_API_KEY",
  "request": { "timeout_seconds": 300 }
}
```

## Seleção Automática de Modelo

Os scripts `auto-commit` e `pr-description` selecionam automaticamente o modelo baseado no tamanho do diff:

| Tokens estimados | Modelo |
|------------------|--------|
| ≤ 128k | `nvidia/nemotron-3-nano-30b-a3b:free` |
| ≤ 256k | `openai/gpt-5-nano` |
| > 256k | `x-ai/grok-4.1-fast` |

## Coding Style & Naming Conventions

- **Python**: PEP 8, 4-space indents, `snake_case` para funções
- **Bash**: POSIX-friendly, usar `shellcheck` para validação
- **CLI options**: kebab-case (`--only-output`, `--max-tokens`)
- Type hints em código Python novo

## Commit & Pull Request Guidelines

Use conventional commit prefixes (`feat:`, `fix:`, `chore:`) com resumos imperativos. O próprio `ab auto-commit` pode ser usado para gerar mensagens.

```bash
# Workflow recomendado
ab auto-commit -a           # Gera e faz commit
ab pr-description -c        # Gera e cria PR
```

## Security & Configuration Tips

- Não commitar `~/.prompt/config.json` ou arquivos com chaves
- Carregar `OPENROUTER_API_KEY` do ambiente
- Evitar ecoar secrets em logs
