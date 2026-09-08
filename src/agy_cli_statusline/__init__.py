# -*- coding: utf-8 -*-
from agy_cli_statusline.installer import cli_main, install, status, uninstall

def main() -> None:
    cli_main()

__all__ = ["main", "cli_main", "install", "uninstall", "status"]
