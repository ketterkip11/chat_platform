import os
from django.contrib.auth import get_user_model
from django.db import transaction

# IMPORTANT: Ensure these imports match your app name exactly
from customercare_chat.models import Conversation, ChatMessage, AgentStatus
from customercare_chat.queries import auto_assign_conversation, assign_oldest_pending_chat

User = get_user_model()

def run_seed_and_test():
    print("--- Cleaning up old test data ---")
    User.objects.filter(username__startswith="test_").delete()
    Conversation.objects.filter(customer__username__startswith="test_").delete()

    print("--- Creating test users ---")
    admin = User.objects.create_superuser(username="test_admin", password="password", email="admin@test.com")
    agent1 = User.objects.create_user(username="test_agent1", password="password", is_staff=True)
    agent2 = User.objects.create_user(username="test_agent2", password="password", is_staff=True)
    customer = User.objects.create_user(username="test_customer", password="password")

    print("--- Bringing agents online ---")
    AgentStatus.objects.update_or_create(user=agent1, defaults={"is_online": True})
    AgentStatus.objects.update_or_create(user=agent2, defaults={"is_online": True})

    print("--- Simulating 15 incoming chats from the customer ---")
    conversations = []
    for i in range(1, 16):
        conv = Conversation.objects.create(customer=customer)
        msg = ChatMessage.objects.create(
            conversation=conv,
            sender=customer,
            message=f"Hello, I need help with issue #{i}!"
        )
        
        # Trigger the load balancer for incoming messages
        auto_assign_conversation(conv)
        conv.refresh_from_db()
        conversations.append(conv)
        
        assigned_name = conv.assigned_to.username if conv.assigned_to else "UNASSIGNED (QUEUE)"
        print(f"   -> Chat #{i} assigned to: {assigned_name}")

    print("\n[PHASE 1: INITIAL ASSIGNMENT RESULTS]")
    agent1_count = Conversation.objects.filter(assigned_to=agent1, is_closed=False).count()
    agent2_count = Conversation.objects.filter(assigned_to=agent2, is_closed=False).count()
    unassigned_count = Conversation.objects.filter(assigned_to__isnull=True, customer=customer, is_closed=False).count()

    print(f"Agent 1 active chats: {agent1_count} (Expected: 4)")
    print(f"Agent 2 active chats: {agent2_count} (Expected: 4)")
    print(f"Unassigned queue:     {unassigned_count} (Expected: 7)")

    if agent1_count == 4 and agent2_count == 4 and unassigned_count == 7:
        print(">> PHASE 1 PASSED: Cap limits successfully enforced.")
    else:
        print(">> PHASE 1 FAILED: Please ensure active_chat_count__lt=4 is in queries.py")

    print("\n--- Simulating Agent 1 closing a chat ---")
    # Get one of Agent 1's active chats and close it
    chat_to_close = Conversation.objects.filter(assigned_to=agent1, is_closed=False).first()
    chat_to_close.is_closed = True
    chat_to_close.save(update_fields=['is_closed'])
    print(f"   -> Closed Chat #{chat_to_close.id}")

    print("--- Agent 1 proactively pulls the next chat from the queue ---")
    # Trigger the pull logic that runs in your view when a chat is closed
    new_chat = assign_oldest_pending_chat(agent1)
    if new_chat:
        print(f"   -> Successfully Pulled Chat #{new_chat.id} from queue and assigned to test_agent1")
    else:
        print("   -> No chat pulled.")

    print("\n[PHASE 2: QUEUE PULL RESULTS]")
    agent1_final_count = Conversation.objects.filter(assigned_to=agent1, is_closed=False).count()
    unassigned_final_count = Conversation.objects.filter(assigned_to__isnull=True, customer=customer, is_closed=False).count()
    
    print(f"Agent 1 active chats: {agent1_final_count} (Expected: 4)")
    print(f"Unassigned queue:     {unassigned_final_count} (Expected: 6)")

    if agent1_final_count == 4 and unassigned_final_count == 6:
        print("\n✅ SUCCESS: The load balancer and queue pull logic are working perfectly!")
    else:
        print("\n❌ FAILURE: The queue pull logic did not yield the expected results.")

if __name__ == "__main__":
    with transaction.atomic():
        run_seed_and_test()