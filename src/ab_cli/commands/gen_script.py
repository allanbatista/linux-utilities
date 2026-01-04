#!/usr/bin/env python3
"""
gen-script - Generate bash/python scripts from natural language descriptions.

Uses LLM to generate executable scripts based on task descriptions.
"""
import argparse
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from ab_cli.core.config import get_config, estimate_tokens, get_language

# ANSI colors
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color


def log_info(msg: str) -> None:
    print(f"{BLUE}[INFO]{NC} {msg}")


def log_success(msg: str) -> None:
    print(f"{GREEN}[SUCCESS]{NC} {msg}")


def log_warning(msg: str) -> None:
    print(f"{YELLOW}[WARNING]{NC} {msg}")


def log_error(msg: str) -> None:
    print(f"{RED}[ERROR]{NC} {msg}", file=sys.stderr)


def find_prompt_command() -> str:
    """Find the ab-prompt command."""
    import shutil

    # Try relative to this file (installed location)
    module_dir = Path(__file__).parent.parent.parent.parent
    prompt_cmd = module_dir / 'bin' / 'ab-prompt'

    if prompt_cmd.exists():
        return str(prompt_cmd)

    # Try in PATH
    if shutil.which('ab-prompt'):
        return 'ab-prompt'

    raise FileNotFoundError("ab-prompt command not found")


def run_cmd(cmd: list[str], default: str = "unknown") -> str:
    """Run a command and return stdout, or default on failure."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return default


def get_system_context() -> str:
    """Get comprehensive system context for script generation."""
    context_parts = []

    # OS info
    os_info = run_cmd(['uname', '-srm'])
    context_parts.append(f"OS: {os_info}")

    # Try to get distro info
    if os.path.exists('/etc/os-release'):
        try:
            with open('/etc/os-release', 'r') as f:
                for line in f:
                    if line.startswith('PRETTY_NAME='):
                        distro = line.split('=', 1)[1].strip().strip('"')
                        context_parts.append(f"Distro: {distro}")
                        break
        except Exception:
            pass

    # Current user
    user = os.environ.get('USER', run_cmd(['whoami']))
    context_parts.append(f"User: {user}")

    # Current directory
    cwd = os.getcwd()
    context_parts.append(f"Current directory: {cwd}")

    # Shell info
    shell = os.environ.get('SHELL', '/bin/bash')
    context_parts.append(f"Shell: {shell}")

    # Bash version
    bash_version = run_cmd(['bash', '--version']).split('\n')[0] if run_cmd(['which', 'bash'], '') else 'not installed'
    context_parts.append(f"Bash: {bash_version}")

    # Python version
    python_version = run_cmd(['python3', '--version'], 'not installed')
    context_parts.append(f"Python: {python_version}")

    # Node version
    node_version = run_cmd(['node', '--version'], 'not installed')
    context_parts.append(f"Node.js: {node_version}")

    # Ruby version
    ruby_version = run_cmd(['ruby', '--version'], 'not installed')
    if ruby_version != 'not installed':
        ruby_version = ruby_version.split()[0:2]
        ruby_version = ' '.join(ruby_version)
    context_parts.append(f"Ruby: {ruby_version}")

    # Perl version
    perl_version = run_cmd(['perl', '-v'])
    if 'not installed' not in perl_version and perl_version:
        match = re.search(r'v(\d+\.\d+\.\d+)', perl_version)
        perl_version = f"perl {match.group(0)}" if match else 'installed'
    else:
        perl_version = 'not installed'
    context_parts.append(f"Perl: {perl_version}")

    # Common tools availability
    tools = []
    for tool in ['curl', 'wget', 'jq', 'git', 'docker', 'kubectl']:
        if run_cmd(['which', tool], '') != '':
            tools.append(tool)
    if tools:
        context_parts.append(f"Available tools: {', '.join(tools)}")

    return '\n'.join(context_parts)


def get_directory_listing(path: str = '.') -> str:
    """Get directory listing."""
    try:
        result = subprocess.run(
            ['ls', '-la', path],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout[:1500]  # Limit size
    except subprocess.CalledProcessError:
        return ""


def get_shebang(lang: str) -> str:
    """Get the appropriate shebang for the language."""
    shebangs = {
        'bash': '#!/usr/bin/env bash',
        'sh': '#!/bin/sh',
        'python': '#!/usr/bin/env python3',
        'python3': '#!/usr/bin/env python3',
        'perl': '#!/usr/bin/env perl',
        'ruby': '#!/usr/bin/env ruby',
        'node': '#!/usr/bin/env node',
    }
    return shebangs.get(lang.lower(), '#!/usr/bin/env bash')


def get_file_extension(lang: str) -> str:
    """Get the appropriate file extension for the language."""
    extensions = {
        'bash': '.sh',
        'sh': '.sh',
        'python': '.py',
        'python3': '.py',
        'perl': '.pl',
        'ruby': '.rb',
        'node': '.js',
    }
    return extensions.get(lang.lower(), '.sh')


def generate_script(description: str, lang: str, script_type: str,
                    system_context: str, dir_listing: str,
                    prompt_cmd: str, output_lang: str,
                    full_script: bool = False) -> str:
    """Generate script using LLM."""
    config = get_config()

    # Determine if we should generate a full script or a minimal one-liner
    if full_script or script_type == 'script':
        # Full script mode - verbose with error handling
        prompt_text = f"""Generate a complete, production-ready {lang} script.

TASK DESCRIPTION:
{description}

SYSTEM ENVIRONMENT:
{system_context}

CURRENT DIRECTORY LISTING:
{dir_listing}

REQUIREMENTS:
1. Return ONLY the script code, no explanations before or after
2. Include appropriate shebang line (#!/usr/bin/env {lang if lang != 'python3' else 'python3'})
3. Use best practices for {lang}:
   - For bash: use set -euo pipefail, quote variables, add usage function
   - For python: use if __name__ == '__main__', handle exceptions, use argparse if needed
4. Add error handling and input validation
5. Include helpful comments to explain complex parts
6. Make the script robust and handle edge cases
7. If the task involves file operations, check if files exist first
8. Use commands and syntax compatible with the system environment above

Generate the complete script:"""
    elif script_type == 'cron':
        # Cron mode - suitable for scheduled execution
        prompt_text = f"""Generate a {lang} script suitable for cron job execution.

TASK DESCRIPTION:
{description}

SYSTEM ENVIRONMENT:
{system_context}

CURRENT DIRECTORY LISTING:
{dir_listing}

REQUIREMENTS:
1. Return ONLY the script code, no explanations before or after
2. Include shebang line
3. No interactive input (cron runs non-interactively)
4. Proper logging to file or syslog
5. Handle errors gracefully
6. Use absolute paths
7. Use commands compatible with the system environment above

Generate the cron script:"""
    else:
        # One-liner mode (default) - minimal output
        prompt_text = f"""Generate the SHORTEST possible {lang} command for this task.

TASK DESCRIPTION:
{description}

SYSTEM ENVIRONMENT:
{system_context}

RULES:
1. Return ONLY the command, nothing else
2. Prefer one-liners whenever possible
3. NO shebang line
4. NO comments
5. NO error handling or validation
6. NO usage functions
7. Direct, copy-paste ready output
8. If truly impossible as one-liner, use minimal lines with semicolons or &&
9. Use environment variables directly without checking if they exist
10. Use commands and syntax compatible with the system environment above

Return ONLY the command:"""

    estimated_tokens = estimate_tokens(prompt_text)
    selected_model = config.select_model(estimated_tokens)

    log_info(f"Using model: {selected_model}")

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(prompt_text)
        prompt_file = f.name

    try:
        result = subprocess.run(
            [prompt_cmd, '--model', selected_model, '--lang', output_lang,
             '--max-completion-tokens', '-1', '--only-output', '--prompt', '-'],
            stdin=open(prompt_file, 'r'),
            capture_output=True,
            text=True,
            check=False
        )

        if result.stderr:
            log_error(result.stderr.strip())

        script = result.stdout.strip()

        # Clean up markdown code fences if present
        if script.startswith('```'):
            lines = script.split('\n')
            # Remove first line (```bash or similar)
            lines = lines[1:]
            # Remove last line if it's just ```
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            script = '\n'.join(lines)

        return script
    finally:
        os.unlink(prompt_file)


def main():
    parser = argparse.ArgumentParser(
        description='Generate scripts from natural language descriptions',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  gen-script "list all files larger than 100MB"      # One-liner output
  gen-script --full "backup database"                # Full script with error handling
  gen-script --type cron "backup daily at 3am"       # Cron-suitable script
  gen-script --lang python "parse CSV sum column 3"  # Python one-liner
  gen-script -o backup.sh "compress and upload"      # Auto-full when saving to file
  gen-script --run "show disk usage"                 # Execute immediately
'''
    )
    parser.add_argument(
        'description',
        nargs='?',
        help='Description of what the script should do'
    )
    parser.add_argument(
        '--lang',
        default='bash',
        choices=['bash', 'sh', 'python', 'python3', 'perl', 'ruby', 'node'],
        help='Script language (default: bash)'
    )
    parser.add_argument(
        '--type',
        dest='script_type',
        default='oneshot',
        choices=['script', 'cron', 'oneshot'],
        help='Type of script (default: oneshot for minimal output)'
    )
    parser.add_argument(
        '--full',
        action='store_true',
        help='Generate complete script with error handling (default: one-liner)'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        help='Output file path (will be made executable)'
    )
    parser.add_argument(
        '--run',
        action='store_true',
        help='Execute the generated script immediately'
    )
    parser.add_argument(
        '-l', '--output-lang',
        default=None,
        help='Output language for comments (default: en)'
    )

    args = parser.parse_args()

    # Get language from config if not specified
    output_lang = args.output_lang or get_language('gen-script')

    if not args.description:
        parser.print_help()
        sys.exit(0)

    # Find prompt command
    try:
        prompt_cmd = find_prompt_command()
    except FileNotFoundError as e:
        log_error(str(e))
        sys.exit(1)

    # Get system and directory context
    log_info("Gathering system context...")
    system_context = get_system_context()
    dir_listing = get_directory_listing()

    # Determine if full script mode is needed
    use_full_script = args.full or args.output is not None

    script_mode = "full script" if use_full_script else "one-liner"
    log_info(f"Generating {args.lang} {script_mode}...")

    script = generate_script(
        args.description, args.lang, args.script_type,
        system_context, dir_listing, prompt_cmd, output_lang,
        full_script=use_full_script
    )

    if not script:
        log_error("Failed to generate script")
        sys.exit(1)

    # Only add shebang for full scripts or when saving to file
    if use_full_script:
        shebang = get_shebang(args.lang)
        if not script.startswith('#!'):
            script = f"{shebang}\n\n{script}"

    print()
    if use_full_script:
        print(f"{GREEN}=== GENERATED SCRIPT ==={NC}")
        print(script)
        print(f"{GREEN}========================{NC}")
    else:
        print(f"{GREEN}=== COMMAND ==={NC}")
        print(script)
        print(f"{GREEN}==============={NC}")
    print()

    # Save to file if requested
    if args.output:
        output_path = Path(args.output)

        # Add extension if not present
        if not output_path.suffix:
            output_path = output_path.with_suffix(get_file_extension(args.lang))

        with open(output_path, 'w') as f:
            f.write(script + '\n')

        # Make executable
        os.chmod(output_path, os.stat(output_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        log_success(f"Script saved to: {output_path}")

    # Execute if requested
    if args.run:
        log_info("Executing script...")
        print()

        # Create temp file for execution
        ext = get_file_extension(args.lang)
        with tempfile.NamedTemporaryFile(mode='w', suffix=ext, delete=False) as f:
            f.write(script + '\n')
            temp_path = f.name

        try:
            os.chmod(temp_path, os.stat(temp_path).st_mode | stat.S_IXUSR)

            # Determine how to execute
            if args.lang in ['python', 'python3']:
                result = subprocess.run(['python3', temp_path], check=False)
            elif args.lang == 'node':
                result = subprocess.run(['node', temp_path], check=False)
            elif args.lang == 'ruby':
                result = subprocess.run(['ruby', temp_path], check=False)
            elif args.lang == 'perl':
                result = subprocess.run(['perl', temp_path], check=False)
            else:
                result = subprocess.run(['bash', temp_path], check=False)

            if result.returncode != 0:
                log_warning(f"Script exited with code: {result.returncode}")
        finally:
            os.unlink(temp_path)


if __name__ == '__main__':
    main()
