"""
ASGI config for chat_platform project.

Routes plain HTTP requests through Django as usual, and WebSocket
connections through Django Channels, wrapped in AuthMiddlewareStack so
consumers see the same logged-in session (self.scope["user"]) as the
rest of the site — no separate WebSocket login step needed.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chat_platform.settings')

# Must be called before importing anything that touches Django models
# (including the app's routing/consumers), so app registry is ready.
django_asgi_app = get_asgi_application()

from customercare_chat.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})