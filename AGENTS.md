# Repository Guidelines

## Project Structure & Module Organization
The repository ships three CLIs. `project-manager` is the Python entry point for the `pm` package (`pm/cli`, `pm/core`, `pm/ai`, `pm/utils`) that drives plan management and AI-assisted workflows; runtime artefacts land in `.project-manager/`. `prompt` is a standalone Python tool for bundling file context and sending it to LLM providers, using `~/.prompt/config.json` for provider defaults. `passgenerator` is a Bash utility for localized password generation. Keep auxiliary assets next to the tool they support and leave `.project-manager/logs` out of commits.

## Build, Test, and Development Commands
Create a virtual environment before hacking:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
Exercise the Project Manager CLI via `./project-manager init`, `./project-manager plan list`, and `./project-manager validate <plan>`, and enable AI planning with `./project-manager plan create --ai`. For the prompt helper, run `python prompt --help` or `python prompt --set-default-model gpt-4o-mini`. Quick-check the Bash tool with `./passgenerator 16 --min-digits 2`.

## Coding Style & Naming Conventions
Follow PEP 8, 4-space indents, and `snake_case` for modules, functions, and Click command names. Keep CLI options kebab-cased and mirror the existing help text tone in `pm/cli/commands.py`. Prefer type hints in new Python code and rely on `rich` formatters for structured output instead of manual ANSI escapes. When touching Bash, stay POSIX-friendly and run `shellcheck passgenerator` locally if available.

## Testing Guidelines
Adopt `pytest` for automation; place test modules under `tests/` mirroring the source layout (e.g., `tests/cli/test_commands.py`). Use `click.testing.CliRunner` with temporary directories to isolate `.project-manager` artefacts. Target each new command or plan mutation path with at least one integration test, and record manual validation steps (CLI transcripts, API calls) in the pull request while a fuller suite is built out.

## Commit & Pull Request Guidelines
Use conventional commit prefixes (`feat:`, `fix:`, `chore:`) with imperative summaries, following the emerging pattern in `git log`. Reference related issues, keep commits scoped, and update docs alongside behavioural changes. Pull requests should include motivation, main changes, test evidence, and configuration updates, plus CLI transcripts or screenshots when adjusting interactive flows.

## AI Planning Flow Notes
- O modo `./project-manager plan create --ai` segue etapas visíveis (Descoberta → Síntese → Confirmação → Finalizado); observe o painel azul no terminal para saber o estágio atual.
- O agente deve sempre gerar um preview com a ferramenta `preview_plan` antes de finalizar; use `/resumo` para reler a última versão.
- Ajustes pontuais disparam o tool `update_plan_field` e exigem um novo preview antes de `finalize_plan`; verifique mensagens verdes/vermelhas para feedback.
- Oriente usuários a `/ajuda` caso esqueçam os comandos rápidos; `cancelar` encerra a sessão com segurança.

## Security & Configuration Tips
Do not commit personal configs from `~/.prompt` or runtime files from `.project-manager/`. Load provider keys (e.g., `OPENAI_API_KEY`, `GEMINI_API_KEY`) from the environment, and avoid echoing secrets to logs. When sharing sample configs, redact tokens and use placeholders such as `YOUR_KEY_HERE`.
