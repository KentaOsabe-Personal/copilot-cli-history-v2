#!/usr/bin/env python
import os
import sys

DEFAULT_SETTINGS_MODULE = "backend_config.settings"


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", DEFAULT_SETTINGS_MODULE)

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
