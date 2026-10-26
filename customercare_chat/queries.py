"""
Read/unread logic for the agent inbox, kept in one place so the inbox
page, the live-refresh endpoint, the nav badge and the WebSocket consumer
all agree on what "unread" means.
"""

from django.db.models import Count, F, Max, OuterRef, Q, Subquery
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import ChatMessage, Conversation, ConversationRead, AgentStatus


def auto_assign_conversation(conversation):
    """
    Assigns a conversation using round-robin distribution to an online agent 
    who has capacity (< 4 active chats) and is NOT a superuser.
    """
    if conversation.assigned_to:
        return  # Already assigned

    from django.contrib.auth import get_user_model
    from django.db.models import Count, Q, Max, F
    User = get_user_model()
    
    # 1. Must be staff
    # 2. Cannot be a superuser/admin
    # 3. Must be actively online
    agents = User.objects.filter(
        is_staff=True,
        is_superuser=False,
        agent_status__is_online=True
    ).annotate(
        # Calculate current capacity (must be under 4)
        active_chat_count=Count(
            'assigned_conversations', 
            filter=Q(assigned_conversations__is_closed=False)
        ),
        # Find the timestamp of the most recent chat assigned to this agent
        last_assigned=Max('assigned_conversations__created_at')
    ).filter(
        active_chat_count__lt=4
    ).order_by(
        # Round Robin: Agents with no previous chats (null) get priority first, 
        # then agents who have waited the longest since their last assignment.
        F('last_assigned').asc(nulls_first=True)
    )

    best_agent = agents.first()
    if best_agent:
        conversation.assigned_to = best_agent
        conversation.save(update_fields=['assigned_to'])
        
        
def assign_oldest_pending_chat(agent):
    """
    Checks if an agent has capacity (< 4 chats). If they do, pulls the oldest 
    unassigned active chat from the queue and assigns it to them.
    Returns the newly assigned conversation, or None.
    """
    # Count the agent's current open chats
    active_count = Conversation.objects.filter(assigned_to=agent, is_closed=False).count()
    
    if active_count < 4:
        # Find the oldest open chat that has no agent assigned
        pending_chat = Conversation.objects.filter(
            assigned_to__isnull=True, 
            is_closed=False
        ).order_by('created_at').first()
        
        if pending_chat:
            pending_chat.assigned_to = agent
            pending_chat.save(update_fields=['assigned_to'])
            return pending_chat
            
    return None


def inbox_conversations(agent):
    """
    Open conversations that have at least one message, newest activity first.
    Each one is annotated for THIS agent with:
      unread_count             customer messages sent after the agent's last_read_at
      last_message_at / _text / _sender_type
    """
    last_read = ConversationRead.objects.filter(
        conversation=OuterRef("pk"), agent=agent
    ).values("last_read_at")[:1]

    latest_message = ChatMessage.objects.filter(
        conversation=OuterRef("pk")
    ).order_by("-timestamp", "-id")

    return (
        Conversation.objects.filter(is_closed=False)
        .select_related("customer", "assigned_to")
        .annotate(
            last_read_at=Subquery(last_read),
            last_message_text=Subquery(latest_message.values("message")[:1]),
            last_message_sender_type=Subquery(latest_message.values("sender_type")[:1]),
        )
        .annotate(
            last_message_at=Max("messages__timestamp"),
            unread_count=Count(
                "messages",
                filter=Q(messages__sender_type=ChatMessage.SenderType.CUSTOMER)
                & (Q(last_read_at__isnull=True) | Q(messages__timestamp__gt=F("last_read_at"))),
            ),
        )
        .filter(last_message_at__isnull=False)
        .order_by("-last_message_at")
    )


def unread_conversation_count(agent):
    """How many conversations have something this agent hasn't read."""
    return inbox_conversations(agent).filter(unread_count__gt=0).count()


def mark_conversation_read(agent, conversation_id, at=None):
    """
    Move this agent's read marker forward to `at` (default: now).
    """
    at = at or timezone.now()
    marker, created = ConversationRead.objects.get_or_create(
        agent=agent,
        conversation_id=conversation_id,
        defaults={"last_read_at": at},
    )
    if not created and marker.last_read_at < at:
        marker.last_read_at = at
        marker.save(update_fields=["last_read_at"])