#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

# SOLUCIÓN: Agregar esto AL INICIO, antes de cualquier import
import site

# Buscar y priorizar el site-packages del entorno virtual
venv_site_packages = None
for path in sys.path:
    if 'antenv' in path and 'site-packages' in path:
        venv_site_packages = path
        break

if venv_site_packages:
    # Remover paths problemáticos del sistema
    sys.path = [p for p in sys.path if '/agents/python' not in p]
    # Poner el entorno virtual primero
    if venv_site_packages in sys.path:
        sys.path.remove(venv_site_packages)
    sys.path.insert(0, venv_site_packages)

def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AI_Backend_Tech_Discount.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()