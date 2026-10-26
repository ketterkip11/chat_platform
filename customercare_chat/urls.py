from django.urls import include, path

from .views import (
    CustomLoginView,
    agent_conversation_view,
    agent_inbox_rows_view,
    agent_inbox_view,
    agent_unread_count_view,
    chat_view,
    register_view,
    guest_start_view,
)

urlpatterns = [
    # Root URL now points directly to the guest chat intake form
    path("", guest_start_view, name="guest_start"),
    
    # Active chat interface
    path("chat/", chat_view, name="chat"),

    # Custom Login handling role-based redirects
    path("login/", CustomLoginView.as_view(), name="login"),

    # Public registration for customers
    path("register/", register_view, name="register"),

    # Built-in Django auth views (logout, password reset flows)
    path("auth/", include("django.contrib.auth.urls")),

    # Agent interface (staff-only)
    path("agent/", agent_inbox_view, name="agent_inbox"),
    path("agent/rows/", agent_inbox_rows_view, name="agent_inbox_rows"),
    path("agent/unread-count/", agent_unread_count_view, name="agent_unread_count"),
    path("agent/<int:conversation_id>/", agent_conversation_view, name="agent_conversation"),
]