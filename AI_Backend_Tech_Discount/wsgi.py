"""
WSGI config for AI_Backend_Tech_Discount project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
import sys

# SOLUCIÓN: Agregar esto AL INICIO, antes de cualquier import
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

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AI_Backend_Tech_Discount.settings')

application = get_wsgi_application()