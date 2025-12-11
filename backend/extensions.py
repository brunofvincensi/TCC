"""
Extensões Flask centralizadas para evitar importações circulares
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Rate limiter - configuração centralizada
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
    strategy="fixed-window",
    headers_enabled=True,  # Habilita headers X-RateLimit-*
    swallow_errors=False  # Não silenciar erros do limiter para debug
)
