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
    list_display = ('id', 'customer', 'assigned_to', 'is_closed', 'created_at')
    list_filter = ('is_closed', 'created_at')
    search_fields = ('customer__username', 'assigned_to__username')
    autocomplete_fields = ('customer', 'assigned_to')
    date_hierarchy = 'created_at'

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