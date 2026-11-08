from .queries import unread_conversation_count


def agent_unread(request):
    """
    Makes `agent_unread_count` available to every template for staff users,
    so the "Queue" badge in the nav is correct on first paint on any page.
    """
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated and user.is_staff:
        return {"agent_unread_count": unread_conversation_count(user)}
    return {}