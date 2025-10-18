import re
from datetime import datetime


def format_duration(seconds: float) -> str:
    """Formata duração em segundos para formato legível"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}min"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"

COLORS_AVAILABLE = False


# Fallback para quando colorama não estiver disponível
class Fore:
    RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ''


class Back:
    RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ''


class Style:
    BRIGHT = DIM = NORMAL = RESET_ALL = ''

class TerminalPrinter:
    """Classe para gerenciar prints formatados no terminal"""

    @staticmethod
    def print_header(text: str):
        """Imprime um cabeçalho destacado"""
        print("\n" + "=" * 80)
        print(f"{Fore.CYAN}{Style.BRIGHT}🚀 {text}{Style.RESET_ALL}")
        print("=" * 80)

    @staticmethod
    def print_subheader(text: str):
        """Imprime um sub-cabeçalho"""
        print(f"\n{Fore.YELLOW}{Style.BRIGHT}▶ {text}{Style.RESET_ALL}")
        print("-" * 60)

    @staticmethod
    def print_info(text: str, indent: int = 0):
        """Imprime informação geral"""
        prefix = "  " * indent + "ℹ️  "
        print(f"{Fore.BLUE}{prefix}{text}{Style.RESET_ALL}")

    @staticmethod
    def print_success(text: str, indent: int = 0):
        """Imprime mensagem de sucesso"""
        prefix = "  " * indent + "✅ "
        print(f"{Fore.GREEN}{Style.BRIGHT}{prefix}{text}{Style.RESET_ALL}")

    @staticmethod
    def print_error(text: str, indent: int = 0):
        """Imprime mensagem de erro"""
        prefix = "  " * indent + "❌ "
        print(f"{Fore.RED}{Style.BRIGHT}{prefix}{text}{Style.RESET_ALL}")

    @staticmethod
    def print_warning(text: str, indent: int = 0):
        """Imprime mensagem de aviso"""
        prefix = "  " * indent + "⚠️  "
        print(f"{Fore.YELLOW}{prefix}{text}{Style.RESET_ALL}")

    @staticmethod
    def print_timing(text: str, duration: float, indent: int = 0):
        """Imprime informação de tempo de execução"""
        prefix = "  " * indent + "⏱️  "
        formatted_duration = format_duration(duration)
        print(f"{Fore.MAGENTA}{prefix}{text}: {formatted_duration}{Style.RESET_ALL}")

    @staticmethod
    def print_claude_message(text: str, message_type: str = "response"):
        """Imprime mensagem do Claude com formatação especial"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        normalized = (message_type or "response").lower()

        # Cabeçalho da mensagem
        if normalized in {"thinking", "thinkingblock"}:
            print(f"\n{Fore.MAGENTA}🤔 [{timestamp}] Claude está pensando...{Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}{Style.DIM}{'─' * 60}{Style.RESET_ALL}")
        elif normalized in {"tool", "tool_use", "tooluseblock"}:
            print(f"\n{Fore.CYAN}🔧 [{timestamp}] Claude usando ferramenta{Style.RESET_ALL}")
            print(f"{Fore.CYAN}{Style.DIM}{'─' * 60}{Style.RESET_ALL}")
        elif normalized == "tool_result":
            print(f"\n{Fore.BLUE}📦 [{timestamp}] Resultado da ferramenta{Style.RESET_ALL}")
            print(f"{Fore.BLUE}{Style.DIM}{'─' * 60}{Style.RESET_ALL}")
        elif normalized == "tool_result_error":
            print(f"\n{Fore.RED}⚠️  [{timestamp}] Erro da ferramenta{Style.RESET_ALL}")
            print(f"{Fore.RED}{Style.DIM}{'─' * 60}{Style.RESET_ALL}")
        elif normalized == "error":
            print(f"\n{Fore.RED}❌ [{timestamp}] Erro{Style.RESET_ALL}")
            print(f"{Fore.RED}{Style.DIM}{'─' * 60}{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.GREEN}🤖 [{timestamp}] Claude responde:{Style.RESET_ALL}")
            print(f"{Fore.GREEN}{Style.DIM}{'─' * 60}{Style.RESET_ALL}")

        # Conteúdo da mensagem com identação
        lines = text.split('\n')
        for line in lines:
            if line.strip():
                # Destaca código
                if line.strip().startswith('```'):
                    print(f"   {Fore.CYAN}{line}{Style.RESET_ALL}")
                # Destaca bullets
                elif line.strip().startswith('-') or line.strip().startswith('*'):
                    print(f"   {Fore.WHITE}{line}{Style.RESET_ALL}")
                # Destaca números
                elif re.match(r'^\s*\d+\.', line):
                    print(f"   {Fore.YELLOW}{line}{Style.RESET_ALL}")
                else:
                    print(f"   {line}")
            else:
                print()

    @staticmethod
    def print_task_status(task_name: str, status: str):
        """Imprime status de uma task com cor apropriada"""
        status_colors = {
            'completed': Fore.GREEN,
            'progress': Fore.YELLOW,
            'failed': Fore.RED,
            'pending': Fore.WHITE
        }

        status_icons = {
            'completed': '✅',
            'progress': '🔄',
            'failed': '❌',
            'pending': '⏳'
        }

        color = status_colors.get(status, Fore.WHITE)
        icon = status_icons.get(status, '❓')

        print(f"{color}{icon} Task: {task_name} [{status.upper()}]{Style.RESET_ALL}")

    @staticmethod
    def print_progress_bar(current: int, total: int, width: int = 50):
        """Imprime uma barra de progresso"""
        if total == 0:
            return

        percentage = current / total
        filled = int(width * percentage)
        bar = '█' * filled + '░' * (width - filled)

        print(f"\n{Fore.CYAN}Progresso: [{bar}] {current}/{total} ({percentage:.1%}){Style.RESET_ALL}")
