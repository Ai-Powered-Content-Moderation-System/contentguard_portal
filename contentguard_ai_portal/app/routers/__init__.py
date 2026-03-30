# Routers package initialization
from app.routers import auth, admin, comments, classification, extraction,notifications

__all__ = [
    'auth',
    'admin',
    'comments',
    'classification',
    'extraction',
    'notifications'
]