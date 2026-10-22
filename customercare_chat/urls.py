from django.urls import include, path

from .views import (
    CustomLoginView,
    agent_conversation_view,
    agent_inbox_rows_view,
    agent_inbox_view,
    agent_unread_count_view,
    chat_view,
    register_view,
)

urlpatterns = [
    # Custom Login handling role-based redirects
    path("login/", CustomLoginView.as_view(), name="login"),

    # Public registration for customers
    path("register/", register_view, name="register"),

    # Built-in Django auth views (logout, password reset flows)
    path("", include("django.contrib.auth.urls")),

    # Customer interface
    path("chat/", chat_view, name="chat"),

    # Agent interface (staff-only)
    path("agent/", agent_inbox_view, name="agent_inbox"),
    path("agent/rows/", agent_inbox_rows_view, name="agent_inbox_rows"),
    path("agent/unread-count/", agent_unread_count_view, name="agent_unread_count"),
    path("agent/<int:conversation_id>/", agent_conversation_view, name="agent_conversation"),
]