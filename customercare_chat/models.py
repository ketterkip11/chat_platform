from django.conf import settings
from django.db import models


class AgentStatus(models.Model):
    """Tracks whether an agent is online for auto-routing."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="agent_status",
    )
    is_online = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user} - {'Online' if self.is_online else 'Offline'}"


class Conversation(models.Model):
    """
    A single chat thread between a customer and an agent.
    """
    class Labels(models.TextChoices):
        GENERAL = "general", "General"
        SUPPORT = "support", "Support"
        SALES = "sales", "Sales"
        URGENT = "urgent", "Urgent"
        BUG = "bug", "Bug"

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_conversations",
    )
    label = models.CharField(
        max_length=20,
        choices=Labels.choices,
        default=Labels.GENERAL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_closed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Conversation #{self.pk} with {self.customer}"


class ChatMessage(models.Model):
    class SenderType(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        AGENT = "agent", "Agent"

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="chat_messages",
    )
    sender_type = models.CharField(
        max_length=10,
        choices=SenderType.choices,
        editable=False,  # never set manually — derived from sender
    )
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    attachment_url = models.URLField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["timestamp"]
        indexes = [
            models.Index(fields=["conversation", "timestamp"]),
        ]

    def save(self, *args, **kwargs):
        if self.sender_id and not self.sender_type:
            self.sender_type = (
                self.SenderType.AGENT if self.sender.is_staff else self.SenderType.CUSTOMER
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.sender_type}] {self.sender}: {self.message[:50]}..."


class ConversationRead(models.Model):
    """
    Per-agent "read up to here" marker for a conversation.
    """
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversation_reads",
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="reads",
    )
    last_read_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["agent", "conversation"],
                name="unique_agent_conversation_read",
            ),
        ]

    def __str__(self):
        return f"{self.agent} read #{self.conversation_id} up to {self.last_read_at:%Y-%m-%d %H:%M:%S}"


class KnowledgeBaseArticle(models.Model):
    """
    Internal digital library/guides for agents. 
    Only editable by admins via the Django Admin panel.
    """
    title = models.CharField(max_length=255)
    content = models.TextField(help_text="Body of the guide. Supports standard text.")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title