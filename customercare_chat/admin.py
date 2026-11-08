from django.contrib import admin
from .models import ChatMessage, Conversation, AgentStatus, KnowledgeBaseArticle

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'sender_type', 'short_message', 'timestamp', 'delivered_at')
    list_filter = ('sender_type', 'timestamp', 'delivered_at')
    search_fields = ('sender__username', 'sender__email', 'message')
    readonly_fields = ('sender_type', 'timestamp')
    autocomplete_fields = ('sender',)
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)

    def short_message(self, obj):
        return obj.message[:75] + ("..." if len(obj.message) > 75 else "")
    short_message.short_description = "Message"


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'client_name', 'agent_name', 'label', 'is_closed', 'created_at')
    list_filter = ('is_closed', 'label', 'created_at')
    search_fields = ('customer__username', 'customer__first_name', 'customer__email', 'assigned_to__username', 'assigned_to__first_name')
    autocomplete_fields = ('customer', 'assigned_to')
    date_hierarchy = 'created_at'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('customer', 'assigned_to')

    def client_name(self, obj):
        if obj.customer.first_name:
            return f"{obj.customer.first_name} ({obj.customer.username})"
        return obj.customer.username
    client_name.short_description = "Client"
    client_name.admin_order_field = "customer__username"

    def agent_name(self, obj):
        if not obj.assigned_to:
            return "-"
        if obj.assigned_to.first_name:
            return f"{obj.assigned_to.first_name} ({obj.assigned_to.username})"
        return obj.assigned_to.username
    agent_name.short_description = "Assigned Agent"
    agent_name.admin_order_field = "assigned_to__username"


@admin.register(AgentStatus)
class AgentStatusAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_online')
    list_filter = ('is_online',)
    search_fields = ('user__username',)
    autocomplete_fields = ('user',)

@admin.register(KnowledgeBaseArticle)
class KnowledgeBaseArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'updated_at')
    list_filter = ('is_active', 'created_at', 'updated_at')
    search_fields = ('title', 'content')