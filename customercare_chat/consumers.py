import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import ChatMessage, Conversation, AgentStatus
from .queries import mark_conversation_read, auto_assign_conversation

AGENT_NOTIFICATIONS_GROUP = "agent_notifications"


def format_time(dt):
    """Cross-platform 'g:i A' style time"""
    return dt.strftime("%I:%M %p").lstrip("0")


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.group_name = f"conversation_{self.conversation_id}"
        user = self.scope["user"]

        if not user.is_authenticated:
            await self.close()
            return

        allowed = await self._user_can_access(user, self.conversation_id)
        if not allowed:
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        text = (data.get("message") or "").strip()
        if not text:
            return

        user = self.scope["user"]
        message, is_first_message = await self._save_message(user, self.conversation_id, text)

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat.message",
                "id": message.id,
                "message": message.message,
                "sender_id": user.id,
                "sender_username": user.username,
                "sender_type": message.sender_type,
                "timestamp": format_time(message.timestamp),
                "attachment_url": message.attachment_url or "",
            },
        )

        if not user.is_staff:
            await self.channel_layer.group_send(
                AGENT_NOTIFICATIONS_GROUP,
                {
                    "type": "agent.notify",
                    "conversation_id": int(self.conversation_id),
                    "customer_username": user.username,
                    "message": message.message,
                    "timestamp": format_time(message.timestamp),
                    "is_new_conversation": is_first_message,
                },
            )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

        user = self.scope["user"]
        if user.is_staff and event["sender_type"] == ChatMessage.SenderType.CUSTOMER:
            await self._mark_read(user, self.conversation_id)

    @database_sync_to_async
    def _user_can_access(self, user, conversation_id):
        if user.is_staff:
            return Conversation.objects.filter(pk=conversation_id).exists()
        return Conversation.objects.filter(pk=conversation_id, customer=user).exists()

    @database_sync_to_async
    def _save_message(self, user, conversation_id, text):
        conversation = Conversation.objects.get(pk=conversation_id)
        message = ChatMessage.objects.create(
            conversation=conversation,
            sender=user,
            message=text,
        )
        is_first = not (
            ChatMessage.objects.filter(conversation=conversation)
            .exclude(pk=message.pk)
            .exists()
        )
        
        # Load balancer trigger: assign chat on the first incoming customer message
        if is_first and not user.is_staff:
            auto_assign_conversation(conversation)

        if user.is_staff:
            mark_conversation_read(user, conversation.pk, at=message.timestamp)
            
        return message, is_first

    @database_sync_to_async
    def _mark_read(self, user, conversation_id):
        mark_conversation_read(user, conversation_id)


class AgentNotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if not user.is_authenticated or not user.is_staff:
            await self.close()
            return

        # Agent is viewing the inbox/chats — flag them as online for assignment
        await self._update_agent_status(user, is_online=True)
        await self.channel_layer.group_add(AGENT_NOTIFICATIONS_GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        user = self.scope["user"]
        if user.is_authenticated and user.is_staff:
            await self._update_agent_status(user, is_online=False)
            
        if hasattr(self, "channel_name"):
            await self.channel_layer.group_discard(AGENT_NOTIFICATIONS_GROUP, self.channel_name)

    @database_sync_to_async
    def _update_agent_status(self, user, is_online):
        status, _ = AgentStatus.objects.get_or_create(user=user)
        status.is_online = is_online
        status.save(update_fields=['is_online'])

    async def agent_notify(self, event):
        await self.send(text_data=json.dumps(event))