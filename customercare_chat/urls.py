from django.urls import include, path

from .views import (
    CustomLoginView,
    agent_conversation_view,
    agent_inbox_rows_view,
    agent_inbox_view,
    agent_unread_count_view,
    agent_dashboard_view,
    agent_reports_view,
    agent_profile_view,
    agent_settings_view,
    agent_knowledge_base_view,
    chat_view,
    register_view,
    guest_start_view,
)

urlpatterns = [
    path("", guest_start_view, name="guest_start"),
    path("chat/", chat_view, name="chat"),
    path("login/", CustomLoginView.as_view(), name="login"),
    path("register/", register_view, name="register"),
    path("auth/", include("django.contrib.auth.urls")),

    path("agent/", agent_inbox_view, name="agent_inbox"),
    path("agent/dashboard/", agent_dashboard_view, name="agent_dashboard"),
    path("agent/reports/", agent_reports_view, name="agent_reports"),
    path("agent/knowledge-base/", agent_knowledge_base_view, name="agent_knowledge_base"),
    path("agent/profile/", agent_profile_view, name="agent_profile"),
    path("agent/settings/", agent_settings_view, name="agent_settings"),
    path("agent/rows/", agent_inbox_rows_view, name="agent_inbox_rows"),
    path("agent/unread-count/", agent_unread_count_view, name="agent_unread_count"),
    path("agent/<int:conversation_id>/", agent_conversation_view, name="agent_conversation"),
]