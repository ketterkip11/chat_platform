import json
from datetime import timedelta
from django import template
from django.utils import timezone
from django.contrib.auth import get_user_model
from customercare_chat.models import Conversation

User = get_user_model()
register = template.Library()

@register.simple_tag(takes_context=True)
def get_dashboard_metrics(context):
    request = context['request']
    now = timezone.localtime(timezone.now())
    
    # 1. Parse Filters from the Request
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    agent_id = request.GET.get('agent_id', 'all')
    
    if start_date_str and end_date_str:
        try:
            start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            end_date = now.date()
            start_date = end_date - timedelta(days=7)
    else:
        end_date = now.date()
        start_date = end_date - timedelta(days=7)

    # 2. Build the Base Queries
    convos = Conversation.objects.all()
    
    if agent_id != 'all' and agent_id.isdigit():
        convos = convos.filter(assigned_to_id=agent_id)
        
    # Time filtering (inclusive of the end_date by going to the very end of the day)
    filter_start = timezone.make_aware(timezone.datetime.combine(start_date, timezone.datetime.min.time()))
    filter_end = timezone.make_aware(timezone.datetime.combine(end_date, timezone.datetime.max.time()))
    
    filtered_convos = convos.filter(created_at__gte=filter_start, created_at__lte=filter_end)

    # 3. Calculate KPIs
    total_convos = filtered_convos.count()
    completed_convos = filtered_convos.filter(is_closed=True).count()
    active_chats = filtered_convos.filter(is_closed=False, assigned_to__isnull=False).count()
    missed_chats = filtered_convos.filter(is_closed=False, assigned_to__isnull=True).count()

    # 4. Agent Performance Breakdown
    agent_names = []
    agent_totals = []
    agent_active = []
    agent_closed = []
    
    if agent_id == 'all':
        staff_users = User.objects.filter(is_staff=True, is_active=True)
    else:
        staff_users = User.objects.filter(pk=agent_id, is_staff=True)

    for staff in staff_users:
        assigned = filtered_convos.filter(assigned_to=staff)
        agent_names.append(staff.first_name or staff.username)
        agent_totals.append(assigned.count())
        agent_active.append(assigned.filter(is_closed=False).count())
        agent_closed.append(assigned.filter(is_closed=True).count())
        
    # 5. Timeline Generation
    delta = end_date - start_date
    days = min(delta.days, 90) # Cap at 90 days to prevent chart overload
    
    ts_labels = []
    ts_data = []
    
    for i in range(days + 1):
        day = start_date + timedelta(days=i)
        ts_labels.append(day.strftime("%b %d"))
        
        day_start = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.min.time()))
        day_end = day_start + timedelta(days=1)
        
        # Timeline respects the agent filter but maps out over the requested date range
        count = convos.filter(
            created_at__gte=day_start,
            created_at__lt=day_end
        ).count()
        ts_data.append(count)
        
    # Fetch all agents for the dropdown selector
    all_agents = list(User.objects.filter(is_staff=True, is_active=True).values('id', 'username', 'first_name'))

    return {
        "start_date": start_date.strftime('%Y-%m-%d'),
        "end_date": end_date.strftime('%Y-%m-%d'),
        "selected_agent": agent_id,
        "all_agents": all_agents,
        "kpis": {
            "total": total_convos,
            "completed": completed_convos,
            "missed": missed_chats,
            "active": active_chats,
        },
        "chart": {
            "labels": json.dumps(ts_labels),
            "data": json.dumps(ts_data),
        },
        "agent_chart": {
            "names": json.dumps(agent_names),
            "totals": json.dumps(agent_totals),
            "active": json.dumps(agent_active),
            "closed": json.dumps(agent_closed),
        }
    }