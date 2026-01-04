#!/usr/bin/env python3
"""
ab config - Manage ab CLI configuration.

Usage:
    ab config show              Display current configuration
    ab config get <key>         Get a specific config value
    ab config set <key> <value> Set a config value
    ab config init              Create default configuration
    ab config path              Show config file path
    ab config edit              Open config in editor
"""
import argparse
import json
import os
import subprocess
import sys

from ab_cli.core.config import get_config, AB_CONFIG_FILE, DEFAULT_CONFIG


def cmd_show(args):
    """Display current configuration."""
    config = get_config()

    if config.config_exists():
        data = config.to_dict()
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(f"No configuration file found at {AB_CONFIG_FILE}")
        print("Using default configuration:")
        print(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False))
        print("\nRun 'ab config init' to create a config file.")


def cmd_get(args):
    """Get a specific config value."""
    config = get_config()
    value = config.get(args.key)

    if value is None:
        # Try to get from defaults
        value = config.get_with_default(args.key)

    if value is None:
        print(f"Key not found: {args.key}", file=sys.stderr)
        sys.exit(1)

    if isinstance(value, (dict, list)):
        print(json.dumps(value, indent=2, ensure_ascii=False))
    else:
        print(value)


def cmd_set(args):
    """Set a config value."""
    config = get_config()

    # Auto-init if config doesn't exist
    if not config.config_exists():
        config.init_config()
        print(f"Created config file at {AB_CONFIG_FILE}")

    # Try to parse value as JSON for complex types
    value = args.value
    try:
        value = json.loads(args.value)
    except json.JSONDecodeError:
        # Keep as string if not valid JSON
        # Handle special string values
        if value.lower() == 'true':
            value = True
        elif value.lower() == 'false':
            value = False
        elif value.isdigit():
            value = int(value)

    config.set(args.key, value)
    print(f"Set {args.key} = {json.dumps(value) if isinstance(value, (dict, list)) else value}")


def cmd_init(args):
    """Create default configuration file."""
    config = get_config()

    if config.config_exists() and not args.force:
        print(f"Config already exists at {AB_CONFIG_FILE}")
        print("Use --force to overwrite.")
        sys.exit(1)

    if config.config_exists():
        # Backup existing
        backup_path = str(AB_CONFIG_FILE) + ".bak"
        os.rename(AB_CONFIG_FILE, backup_path)
        print(f"Backed up existing config to {backup_path}")

    # Reset singleton to force reload
    config._loaded = False
    config._config = {}

    config.init_config()
    print(f"Created default config at {AB_CONFIG_FILE}")


def cmd_path(args):
    """Show config file path."""
    print(AB_CONFIG_FILE)


def cmd_edit(args):
    """Open config in editor."""
    config = get_config()

    if not config.config_exists():
        config.init_config()
        print(f"Created config file at {AB_CONFIG_FILE}")

    editor = os.environ.get('EDITOR', os.environ.get('VISUAL', 'nano'))
    subprocess.run([editor, str(AB_CONFIG_FILE)])


def cmd_list_keys(args):
    """List all available config keys."""
    def list_keys(d, prefix=''):
        keys = []
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                keys.extend(list_keys(v, key))
            else:
                keys.append(key)
        return keys

    for key in sorted(list_keys(DEFAULT_CONFIG)):
        print(key)


def cmd_clear_history(args):
    """Clear LLM interaction history."""
    from ab_cli.core.config import AB_HISTORY_DIR

    if not AB_HISTORY_DIR.exists():
        print("No history directory found.")
        return

    # Count files
    history_files = list(AB_HISTORY_DIR.glob("history_*.json"))
    index_file = AB_HISTORY_DIR / "index.json"

    total_files = len(history_files) + (1 if index_file.exists() else 0)

    if total_files == 0:
        print("No history files found.")
        return

    if not args.yes:
        confirm = input(f"Delete {total_files} history files? (y/N) ").strip().lower()
        if confirm != 'y':
            print("Cancelled.")
            return

    # Delete files
    deleted = 0
    for f in history_files:
        try:
            f.unlink()
            deleted += 1
        except OSError:
            pass

    if index_file.exists():
        try:
            index_file.unlink()
            deleted += 1
        except OSError:
            pass

    print(f"Deleted {deleted} history files.")


def main():
    parser = argparse.ArgumentParser(
        description='Manage ab CLI configuration',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  ab config show
  ab config get global.language
  ab config set global.language pt-br
  ab config set models.small 'anthropic/claude-3-haiku'
  ab config init
  ab config edit

Keys use dot notation: global.language, models.small, etc.
'''
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # show
    subparsers.add_parser('show', help='Display current configuration')

    # get
    get_parser = subparsers.add_parser('get', help='Get a specific config value')
    get_parser.add_argument('key', help='Config key (dot notation)')

    # set
    set_parser = subparsers.add_parser('set', help='Set a config value')
    set_parser.add_argument('key', help='Config key (dot notation)')
    set_parser.add_argument('value', help='Value to set')

    # init
    init_parser = subparsers.add_parser('init', help='Create default configuration')
    init_parser.add_argument('--force', '-f', action='store_true',
                             help='Overwrite existing config')

    # path
    subparsers.add_parser('path', help='Show config file path')

    # edit
    subparsers.add_parser('edit', help='Open config in editor')

    # list-keys
    subparsers.add_parser('list-keys', help='List all available config keys')

    # clear-history
    clear_history_parser = subparsers.add_parser(
        'clear-history', help='Clear LLM interaction history')
    clear_history_parser.add_argument(
        '-y', '--yes', action='store_true', help='Skip confirmation prompt')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    commands = {
        'show': cmd_show,
        'get': cmd_get,
        'set': cmd_set,
        'init': cmd_init,
        'path': cmd_path,
        'edit': cmd_edit,
        'list-keys': cmd_list_keys,
        'clear-history': cmd_clear_history,
    }

    commands[args.command](args)


if __name__ == '__main__':
    main()
