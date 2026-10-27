import json
from datetime import timedelta
from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login, get_user_model
from django.contrib.auth.views import LoginView
from django.http import JsonResponse
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
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    dates_labels = []
    chats_data = []
    
    for i in range(6, -1, -1):
        day_start = start_of_today - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        dates_labels.append(day_start.strftime("%b %d"))
        
        count = Conversation.objects.filter(
            assigned_to=request.user,
            created_at__gte=day_start,
            created_at__lt=day_end
        ).count()
        chats_data.append(count)

    return render(request, "agent_reports.html", {
        "chart_labels": json.dumps(dates_labels),
        "chart_data": json.dumps(chats_data),
    })

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
    })


@never_cache
@staff_member_required(login_url="login")
def agent_inbox_rows_view(request):
    return render(request, "_queue_rows_2.html", {
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

    if request.method == "POST" and "close_conversation" in request.POST:
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

    return render(request, "agent_conversation.html", {
        "conversation": conversation,
        "messages": messages,
    })