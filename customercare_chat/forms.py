from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import ChatMessage, Conversation

User = get_user_model()


class CustomerSignupForm(UserCreationForm):
    """
    Public self-registration form. Every account created here is a
    customer — `is_staff` is never exposed as a field, so it's left at
    the model default (False) no matter what. Agents are never created
    through this form; they're designated separately by a superuser
    flipping is_staff in the Django admin (or a dedicated internal
    "add agent" flow that itself requires staff/superuser access).
    """
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.is_staff = False  # explicit, even though it's already the default
        if commit:
            user.save()
        return user


class ChatMessageForm(forms.ModelForm):
    """
    Form used by both customers and agents to send a message into an
    existing conversation.

    Deliberately excludes `conversation`, `sender`, and `sender_type` —
    none of these should ever come from user input:
      - `sender` / `sender_type` are set server-side from `request.user`
        (see ChatMessage.save(), which derives sender_type automatically).
      - `conversation` is set server-side from the URL (e.g. a
        conversation_id in the view's kwargs), never from the form body —
        otherwise a user could post into someone else's conversation by
        editing a hidden field.
    """

    class Meta:
        model = ChatMessage
        fields = ['message', 'attachment_url']
        widgets = {
            'message': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Type your message...',
                'class': 'chat-message-input',
                'autofocus': True,
            }),
            'attachment_url': forms.URLInput(attrs={
                'placeholder': 'https://...',
                'class': 'chat-attachment-input',
            }),
        }
        labels = {
            'message': '',
            'attachment_url': 'Attachment (optional)',
        }

    def clean_message(self):
        message = self.cleaned_data.get('message', '').strip()
        if not message:
            raise forms.ValidationError("Message cannot be empty.")
        return message


class ChatMessageAdminForm(forms.ModelForm):
    """
    Form for staff/admin use where conversation and sender need to be
    picked manually (e.g. backfilling data or testing) rather than
    pulled from request.user and the URL.

    `sender_type` is still left out — it's derived automatically in the
    model's save() method and should never be hand-set, even by an admin.
    """

    class Meta:
        model = ChatMessage
        fields = ['conversation', 'sender', 'message', 'attachment_url', 'delivered_at']
        widgets = {
            'delivered_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }


class ConversationForm(forms.ModelForm):
    """
    Lets a logged-in customer start a new conversation. `customer` is
    excluded and set server-side from request.user in the view, for the
    same reason sender is excluded above — never trust it from the form.
    """

    class Meta:
        model = Conversation
        fields = []  # no user-editable fields; customer and timestamps are server-set

    def save(self, customer, commit=True):
        conversation = super().save(commit=False)
        conversation.customer = customer
        if commit:
            conversation.save()
        return conversation