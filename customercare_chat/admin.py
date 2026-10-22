from django.contrib import admin

from .models import ChatMessage


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