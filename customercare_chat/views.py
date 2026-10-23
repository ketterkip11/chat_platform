from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .forms import CustomerSignupForm
from .models import Conversation
from .queries import (
    inbox_conversations,
    mark_conversation_read,
    unread_conversation_count,
    assign_oldest_pending_chat,
)


def get_user_home_redirect(user):
    """Routing helper that redirects authenticated users based on role."""
    if user.is_superuser:
        return redirect("/admin/")
    if user.is_staff:
        return redirect("agent_inbox")
    return redirect("chat")


class CustomLoginView(LoginView):
    """Custom LoginView enforcing role-based landing page redirects."""
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
            return "/agent/"
        return "/chat/"


def register_view(request):
    """Public self-registration for customers."""
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
@login_required
def chat_view(request):
    """Customer chat view. Redirects staff and admins to their respective dashboards."""
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
@staff_member_required(login_url="chat")
def agent_inbox_view(request):
    """The agent's inbox containing all open conversations."""
    return render(request, "agent_inbox.html", {
        "conversations": inbox_conversations(request.user),
    })


@never_cache
@staff_member_required(login_url="chat")
def agent_inbox_rows_view(request):
    """HTML fragment view for live queue refreshes via AJAX."""
    return render(request, "_queue_rows_2.html", {
        "conversations": inbox_conversations(request.user),
    })


@never_cache
@staff_member_required(login_url="chat")
def agent_unread_count_view(request):
    """JSON endpoint for agent unread message count."""
    return JsonResponse({"unread": unread_conversation_count(request.user)})


@never_cache
@staff_member_required(login_url="chat")
def agent_conversation_view(request, conversation_id):
    """Renders a single conversation thread for the agent panel."""
    conversation = get_object_or_404(Conversation, pk=conversation_id)

    if request.method == "POST" and "close_conversation" in request.POST:
        # Close the current conversation
        conversation.is_closed = True
        conversation.save(update_fields=["is_closed"])

        # Attempt to auto-assign the next pending chat in the queue to this agent
        new_chat = assign_oldest_pending_chat(request.user)

        # Notify the agent via WebSocket if a new chat was successfully assigned
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