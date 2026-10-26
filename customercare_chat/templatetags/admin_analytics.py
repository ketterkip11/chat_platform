import json
from django import template
from django.utils import timezone
from datetime import timedelta
from customercare_chat.models import Conversation

register = template.Library()

@register.simple_tag
def get_dashboard_metrics():
    # Anchor to the exact start of today in the active timezone
    now = timezone.localtime(timezone.now())
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # KPIs
    total_convos = Conversation.objects.count()
    completed_convos = Conversation.objects.filter(is_closed=True).count()
    missed_chats = Conversation.objects.filter(is_closed=False, assigned_to__isnull=True).count()
    active_chats = Conversation.objects.filter(is_closed=False, assigned_to__isnull=False).count()
    
    # Chart Data: Activity over last 7 days
    dates_labels = []
    chats_data = []
    
    for i in range(6, -1, -1):
        day_start = start_of_today - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        
        dates_labels.append(day_start.strftime("%b %d"))
        
        # Safe range filtering that bypasses SQLite's date extraction limits
        count = Conversation.objects.filter(
            created_at__gte=day_start,
            created_at__lt=day_end
        ).count()
        chats_data.append(count)

    return {
        "kpis": {
            "total": total_convos,
            "completed": completed_convos,
            "missed": missed_chats,
            "active": active_chats,
        },
        "chart": {
            "labels": json.dumps(dates_labels),
            "data": json.dumps(chats_data),
        }
    }