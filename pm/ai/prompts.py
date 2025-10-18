"""System prompts and templates for AI-powered plan generation."""

import os

file_path = os.path.dirname(os.path.realpath(__file__))

with open(os.path.join(file_path,  "prompts/planner.md")) as f:
    PLAN_SYSTEM_PROMPT = f.read()


INITIAL_PROMPT = """Conte brevemente o projeto que deseja planejar (contexto, objetivo principal, perfil de usuários)."""


CONFIRMATION_TEMPLATE = """
Com base na nossa conversa, aqui está o plano proposto:

📝 **Nome**: {name}
📄 **Brief**: {brief}

🎯 **Objetivos**:
{objectives}

📦 **Deliverables**:
{deliverables}

{tags_section}
{author_section}

Está satisfeito com o plano? Você pode:
- Confirmar: "sim", "pode criar", "perfeito"
- Refinar: "mudar X para Y", "adicionar Z aos objetivos"
- Cancelar: "cancelar", "desistir"
"""
