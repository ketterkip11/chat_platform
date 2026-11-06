import json
import csv
from datetime import timedelta
from django.utils import timezone
from django.core.files.storage import FileSystemStorage
from django.views.decorators.http import require_POST
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login, get_user_model
from django.contrib.auth.views import LoginView
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.crypto import get_random_string
from django.views.decorators.cache import never_cache

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .forms import CustomerSignupForm
from .models import Conversation, KnowledgeBaseArticle
from .queries import (
    inbox_conversations,
    mark_conversation_read,
    unread_conversation_count,
    assign_oldest_pending_chat,
)

User = get_user_model()


def get_user_home_redirect(user):
    if user.is_superuser:
        return redirect("/admin/")
    if user.is_staff:
        return redirect("agent_dashboard")
    return redirect("chat")


class CustomLoginView(LoginView):
    template_name = "login.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return get_user_home_redirect(request.user)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        next_url = self.request.POST.get("next") or self.request.GET.get("next")
        if next_url:
            return next_url
        if self.request.user.is_superuser:
            return "/admin/"
        if self.request.user.is_staff:
            return "/agent/dashboard/"
        return "/chat/"


def register_view(request):
    if request.user.is_authenticated:
        return get_user_home_redirect(request.user)

    if request.method == "POST":
        form = CustomerSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("chat")
    else:
        form = CustomerSignupForm()

    return render(request, "register.html", {"form": form})


# ---------------------------------------------------------------------------
# Customer Routes
# ---------------------------------------------------------------------------

@never_cache
def guest_start_view(request):
    if request.user.is_authenticated:
        return get_user_home_redirect(request.user)

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()

        if name and email:
            safe_name = "".join(c for c in name if c.isalnum())
            guest_username = f"{safe_name.lower()}_{get_random_string(5)}"
            
            user = User.objects.create_user(
                username=guest_username[:150], 
                email=email,
                first_name=name[:150]
            )
            login(request, user)
            return redirect("chat")
        
        return render(request, "guest_start.html", {"error": "Please provide both your name and email."})

    return render(request, "guest_start.html")


@never_cache
def chat_view(request):
    if not request.user.is_authenticated:
        return redirect("guest_start")
        
    if request.user.is_staff or request.user.is_superuser:
        return get_user_home_redirect(request.user)

    conversation, _ = Conversation.objects.get_or_create(
        customer=request.user,
        is_closed=False,
    )

    messages = (
        conversation.messages
        .select_related("sender")
        .order_by("timestamp")
    )

    return render(request, "index.html", {
        "messages": messages,
        "conversation": conversation,
    })


@never_cache
@require_POST
def upload_attachment_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    file = request.FILES.get('file')
    if not file:
        return JsonResponse({'error': 'No file provided'}, status=400)
        
    fs = FileSystemStorage()
    filename = fs.save(file.name, file)
    file_url = fs.url(filename)
    
    return JsonResponse({'url': file_url})


# ---------------------------------------------------------------------------
# Agent Routes (Staff / Admin Only)
# ---------------------------------------------------------------------------

@never_cache
@staff_member_required(login_url="login")
def agent_dashboard_view(request):
    active_chats = Conversation.objects.filter(assigned_to=request.user, is_closed=False).count()
    closed_chats = Conversation.objects.filter(assigned_to=request.user, is_closed=True).count()
    
    return render(request, "agent_dashboard.html", {
        "active_chats": active_chats,
        "closed_chats": closed_chats,
    })


@never_cache
@staff_member_required(login_url="login")
def agent_reports_view(request):
    now = timezone.localtime(timezone.now())
    is_admin = request.user.is_superuser
    
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    if start_date_str and end_date_str:
        try:
            start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            end_date = now.date()
            start_date = end_date - timedelta(days=30)
    else:
        end_date = now.date()
        start_date = end_date - timedelta(days=30)

    if is_admin:
        base_convos = Conversation.objects.all()
    else:
        base_convos = Conversation.objects.filter(assigned_to=request.user)

    total_convos = base_convos.count()
    closed_convos = base_convos.filter(is_closed=True).count()
    active_convos = base_convos.filter(is_closed=False, assigned_to__isnull=False).count()
    missed_convos = base_convos.filter(is_closed=False, assigned_to__isnull=True).count() if is_admin else 0
    
    agent_names = []
    agent_totals = []
    agent_active = []
    agent_closed = []

    if is_admin:
        staff_users = User.objects.filter(is_staff=True, is_active=True)
        for staff in staff_users:
            assigned = Conversation.objects.filter(assigned_to=staff)
            agent_names.append(staff.first_name or staff.username)
            agent_totals.append(assigned.count())
            agent_active.append(assigned.filter(is_closed=False).count())
            agent_closed.append(assigned.filter(is_closed=True).count())

    delta = end_date - start_date
    days = min(delta.days, 90) 
    
    ts_labels = []
    ts_data = []
    
    for i in range(days + 1):
        day = start_date + timedelta(days=i)
        ts_labels.append(day.strftime("%b %d"))
        
        day_start = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.min.time()))
        day_end = day_start + timedelta(days=1)
        
        count = base_convos.filter(
            created_at__gte=day_start,
            created_at__lt=day_end
        ).count()
        ts_data.append(count)

    return render(request, "agent_reports.html", {
        "start_date": start_date.strftime('%Y-%m-%d'),
        "end_date": end_date.strftime('%Y-%m-%d'),
        "is_admin": is_admin,
        
        "total_convos": total_convos,
        "closed_convos": closed_convos,
        "active_convos": active_convos,
        "missed_convos": missed_convos,
        
        "agent_names": json.dumps(agent_names),
        "agent_totals": json.dumps(agent_totals),
        "agent_active": json.dumps(agent_active),
        "agent_closed": json.dumps(agent_closed),
        
        "ts_labels": json.dumps(ts_labels),
        "ts_data": json.dumps(ts_data),
    })


@never_cache
@staff_member_required(login_url="login")
def export_reports_view(request):
    """Generates an Excel compatible CSV report export."""
    now = timezone.localtime(timezone.now())
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    agent_id = request.GET.get('agent_id', 'all')

    try:
        start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else (now.date() - timedelta(days=30))
        end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else now.date()
    except ValueError:
        end_date = now.date()
        start_date = end_date - timedelta(days=30)

    filter_start = timezone.make_aware(timezone.datetime.combine(start_date, timezone.datetime.min.time()))
    filter_end = timezone.make_aware(timezone.datetime.combine(end_date, timezone.datetime.max.time()))

    if request.user.is_superuser:
        convos = Conversation.objects.filter(created_at__gte=filter_start, created_at__lte=filter_end)
        if agent_id != 'all' and agent_id.isdigit():
            convos = convos.filter(assigned_to_id=agent_id)
    else:
        convos = Conversation.objects.filter(assigned_to=request.user, created_at__gte=filter_start, created_at__lte=filter_end)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="chat_report_{start_date}_to_{end_date}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Chat ID', 'Customer Name', 'Customer Email', 'Assigned Agent', 'Label', 'Date Created', 'Status'])

    for c in convos.select_related('customer', 'assigned_to'):
        agent_name = c.assigned_to.first_name or c.assigned_to.username if c.assigned_to else "Unassigned"
        status = "Closed" if c.is_closed else "Active"
        writer.writerow([
            c.pk, 
            c.customer.first_name or c.customer.username, 
            c.customer.email, 
            agent_name,
            c.get_label_display(),
            c.created_at.strftime("%Y-%m-%d %H:%M:%S"), 
            status
        ])
        
    return response


@never_cache
@staff_member_required(login_url="login")
def agent_knowledge_base_view(request):
    articles = KnowledgeBaseArticle.objects.filter(is_active=True)
    return render(request, "agent_knowledge_base.html", {"articles": articles})


@never_cache
@staff_member_required(login_url="login")
def agent_profile_view(request):
    if request.method == "POST":
        request.user.first_name = request.POST.get("first_name", "").strip()
        request.user.email = request.POST.get("email", "").strip()
        request.user.save(update_fields=["first_name", "email"])
        return redirect("agent_profile")
        
    return render(request, "agent_profile.html")


@never_cache
@staff_member_required(login_url="login")
def agent_settings_view(request):
    return render(request, "agent_settings.html")


@never_cache
@staff_member_required(login_url="login")
def agent_inbox_view(request):
    return render(request, "agent_inbox.html", {
        "conversations": inbox_conversations(request.user),
        "labels": Conversation.Labels.choices,
    })


@never_cache
@staff_member_required(login_url="login")
def agent_inbox_rows_view(request):
    return render(request, "_queue_rows.html", {
        "conversations": inbox_conversations(request.user),
    })


@never_cache
@staff_member_required(login_url="login")
def agent_unread_count_view(request):
    return JsonResponse({"unread": unread_conversation_count(request.user)})


@never_cache
@staff_member_required(login_url="login")
def agent_conversation_view(request, conversation_id):
    conversation = get_object_or_404(Conversation, pk=conversation_id)

    if request.method == "POST":
        if "close_conversation" in request.POST:
            conversation.is_closed = True
            conversation.save(update_fields=["is_closed"])
            
            new_chat = assign_oldest_pending_chat(request.user)
            if new_chat:
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    "agent_notifications",
                    {
                        "type": "agent.notify",
                        "conversation_id": new_chat.pk,
                        "customer_username": new_chat.customer.username,
                        "message": "Auto-assigned from the waiting queue.",
                        "is_new_conversation": True,
                    }
                )
            return redirect("agent_inbox")
            
        elif "reassign_conversation" in request.POST:
            new_agent_id = request.POST.get("new_agent_id")
            if new_agent_id:
                new_agent = get_object_or_404(User, pk=new_agent_id, is_staff=True)
                conversation.assigned_to = new_agent
                conversation.save(update_fields=["assigned_to"])

                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    "agent_notifications",
                    {
                        "type": "agent.notify",
                        "conversation_id": conversation.pk,
                        "customer_username": conversation.customer.username,
                        "message": f"Chat reassigned to you by {request.user.first_name or request.user.username}.",
                        "is_new_conversation": True,
                    }
                )
            return redirect("agent_inbox")
            
        elif "update_label" in request.POST:
            new_label = request.POST.get("label")
            if new_label in dict(Conversation.Labels.choices):
                conversation.label = new_label
                conversation.save(update_fields=["label"])
                
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    "agent_notifications",
                    {
                        "type": "agent.notify",
                        "conversation_id": conversation.pk,
                        "customer_username": conversation.customer.username,
                        "message": f"Category updated to {dict(Conversation.Labels.choices).get(new_label)}.",
                        "is_new_conversation": False,
                    }
                )
            return redirect("agent_inbox")

    messages = list(
        conversation.messages
        .select_related("sender")
        .order_by("timestamp")
    )

    mark_conversation_read(
        request.user,
        conversation.pk,
        at=messages[-1].timestamp if messages else None,
    )

    available_agents = User.objects.filter(is_staff=True, is_active=True).exclude(pk=request.user.pk)

    return render(request, "agent_conversation.html", {
        "conversation": conversation,
        "messages": messages,
        "available_agents": available_agents,
        "conversations": inbox_conversations(request.user),
        "labels": Conversation.Labels.choices,
    })