import json
from django import template
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
from customercare_chat.models import Conversation, ChatMessage

register = template.Library()

@register.simple_tag
def get_dashboard_metrics():
    today = timezone.now()
    last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    
    # KPIs
    total_convos = Conversation.objects.count()
    completed_convos = Conversation.objects.filter(is_closed=True).count()
    missed_chats = Conversation.objects.filter(is_closed=False, assigned_to__isnull=True).count()
    active_chats = Conversation.objects.filter(is_closed=False, assigned_to__isnull=False).count()
    
    # Chart Data: Activity over last 7 days
    dates_labels = [d.strftime("%b %d") for d in last_7_days]
    chats_data = []
    
    for day in last_7_days:
        count = Conversation.objects.filter(
            created_at__year=day.year,
            created_at__month=day.month,
            created_at__day=day.day
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