from django.core.exceptions import PermissionDenied
from django.http import Http404
from .models import Document, DocumentShare


def get_user_document_permission(document, user):
    """
    Returns 'owner', 'editor', 'viewer', or None.
    """
    if not user.is_authenticated:
        return None
    if document.owner_id == user.id:
        return 'owner'
    share = document.shares.filter(user=user).first()
    if share:
        return share.permission
    return None


def get_document_permission(document, user):
    """Alias for get_user_document_permission."""
    return get_user_document_permission(document, user)


def can_delete(document, user):
    """Returns True if the user is the owner of the document."""
    return user.is_authenticated and document.owner_id == user.id


def can_edit(document, user):
    """Returns True if user has edit rights (owner or editor share)."""
    return get_user_document_permission(document, user) in ('owner', 'editor')


def get_document_or_404_for_user(pk, user):
    """
    Retrieve document by pk, ensuring the user has at least view permission.
    Returns (document, permission_str).
    Raises Http404 if not found or if the user has no access (to prevent ID guessing).
    """
    try:
        document = Document.objects.select_related('owner').get(pk=pk)
    except Document.DoesNotExist:
        raise Http404("Document not found.")

    permission = get_user_document_permission(document, user)
    if permission is None:
        raise Http404("Document not found.")

    return document, permission
