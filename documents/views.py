import json
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import SignUpForm
from .importers import DocumentImportError, validate_and_process_upload
from .models import Document, DocumentShare
from .permissions import can_delete, get_document_permission
from .sanitizer import sanitize_document_html

User = get_user_model()


def signup(request):
    """Register a new user account with username and unique email."""
    if request.user.is_authenticated:
        return redirect('documents:dashboard')

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome to Draftly, {user.username}!')
            return redirect('documents:dashboard')
    else:
        form = SignUpForm()

    return render(request, 'registration/signup.html', {'form': form})


@login_required
def dashboard(request):
    """Document dashboard displaying documents owned by and shared with the user."""
    query = request.GET.get('q', '').strip()

    owned_documents = Document.objects.filter(owner=request.user).select_related('owner')
    shared_shares = DocumentShare.objects.filter(user=request.user).select_related('document__owner')

    if query:
        owned_documents = owned_documents.filter(title__icontains=query)
        shared_shares = shared_shares.filter(document__title__icontains=query)

    return render(request, 'documents/dashboard.html', {
        'owned_documents': owned_documents,
        'shared_documents': shared_shares,
        'shared_shares': shared_shares,
        'search_query': query,
        'query': query,
        'owned_count': owned_documents.count(),
        'shared_count': shared_shares.count(),
    })


@login_required
@require_POST
def create_document(request):
    """Create a new document and immediately redirect to its editor."""
    document = Document.objects.create(
        title='Untitled Document',
        content='',
        owner=request.user,
    )
    return redirect('documents:editor', pk=document.pk)


@login_required
def import_document(request):
    """
    Handles file upload and imports .txt or .md files into a new Document.
    GET: renders a dedicated import page.
    POST: validates file, creates document, and redirects to editor on success.
    """
    if request.method == 'POST':
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            messages.error(request, "Please select a file to import.")
            if request.POST.get('from_page') == '1':
                return render(request, 'documents/import.html', {'error': 'Please select a file to import.'})
            return redirect('documents:dashboard')

        try:
            title, content = validate_and_process_upload(uploaded_file)
            document = Document.objects.create(
                owner=request.user,
                title=title,
                content=content,
            )
            messages.success(request, f'Document "{document.title}" was imported successfully.')
            return redirect('documents:editor', pk=document.pk)
        except DocumentImportError as e:
            messages.error(request, str(e))
            if request.POST.get('from_page') == '1':
                return render(request, 'documents/import.html', {'error': str(e)})
            return redirect('documents:dashboard')
        except Exception:
            err_msg = "An unexpected error occurred while processing the file."
            messages.error(request, err_msg)
            if request.POST.get('from_page') == '1':
                return render(request, 'documents/import.html', {'error': err_msg})
            return redirect('documents:dashboard')

    return render(request, 'documents/import.html')


@login_required
def editor(request, pk):
    """Rich-text document editor view with access control."""
    document = get_object_or_404(Document, pk=pk)
    permission = get_document_permission(document, request.user)

    if permission is None:
        raise Http404("Document not found.")

    can_edit_flag = permission in ('owner', 'editor')
    is_owner = permission == 'owner'
    shares = document.shares.select_related('user').all() if is_owner else []

    return render(request, 'documents/editor.html', {
        'document': document,
        'can_edit': can_edit_flag,
        'is_owner': is_owner,
        'permission': permission,
        'shares': shares,
    })


@login_required
@require_POST
def save_document(request, pk):
    """JSON autosave endpoint for updating document title and sanitized rich text content."""
    document = get_object_or_404(Document, pk=pk)
    permission = get_document_permission(document, request.user)

    if permission is None:
        return JsonResponse({'error': 'Document not found or access denied.'}, status=404)

    if permission == 'viewer':
        return JsonResponse({'error': 'Viewers cannot modify this document.'}, status=403)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)

    title = data.get('title', '').strip()
    if not title:
        title = 'Untitled Document'
    elif len(title) > 255:
        return JsonResponse({'error': 'Title must be 255 characters or fewer.'}, status=400)

    raw_content = data.get('content', '')
    sanitized_content = sanitize_document_html(raw_content)

    document.title = title
    document.content = sanitized_content
    document.save()

    return JsonResponse({
        'status': 'saved',
        'title': document.title,
        'updated_at': document.updated_at.strftime('%b %d, %Y, %I:%M %p'),
    })


@login_required
@require_POST
def delete_document(request, pk):
    """Delete a document (restricted to the document owner)."""
    document = get_object_or_404(Document, pk=pk)

    if not can_delete(document, request.user):
        return HttpResponseForbidden("Only the document owner can delete this document.")

    title = document.title
    document.delete()
    messages.success(request, f'Document "{title}" was deleted.')
    return redirect('documents:dashboard')


def _get_owned_document_or_json_error(pk, user):
    """
    Returns (document, None) if user is the document owner,
    otherwise (None, JsonResponse) with 404 (stranger/missing) or 403 (non-owner).
    """
    try:
        document = Document.objects.select_related('owner').get(pk=pk)
    except Document.DoesNotExist:
        return None, JsonResponse({'error': 'Document not found.'}, status=404)

    permission = get_document_permission(document, user)
    if permission is None:
        return None, JsonResponse({'error': 'Document not found.'}, status=404)
    if permission != 'owner':
        return None, JsonResponse({'error': 'Only the document owner can manage sharing.'}, status=403)

    return document, None


def _parse_request_payload(request):
    """Parse JSON body if content-type is JSON, otherwise return request.POST."""
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            return None
    return request.POST


@login_required
@require_POST
def share_document(request, pk):
    """Grant a registered user Viewer or Editor access to a document by email."""
    document, error_response = _get_owned_document_or_json_error(pk, request.user)
    if error_response:
        return error_response

    data = _parse_request_payload(request)
    if data is None:
        return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)

    email = (data.get('email') or '').strip()
    permission = (data.get('permission') or '').strip().lower()

    if not email:
        return JsonResponse({'error': 'Please enter an email address.'}, status=400)

    valid_permissions = {
        DocumentShare.Permission.VIEWER,
        DocumentShare.Permission.EDITOR,
    }
    if permission not in valid_permissions:
        return JsonResponse({'error': 'Invalid permission. Choose viewer or editor.'}, status=400)

    recipient = User.objects.filter(email__iexact=email).first()
    if not recipient:
        return JsonResponse({'error': f'No registered user found with email "{email}".'}, status=404)

    if recipient.id == document.owner_id:
        return JsonResponse({'error': 'You cannot share a document with yourself.'}, status=400)

    if DocumentShare.objects.filter(document=document, user=recipient).exists():
        return JsonResponse({'error': f'{recipient.email} already has access to this document.'}, status=400)

    try:
        share = DocumentShare.objects.create(
            document=document,
            user=recipient,
            permission=permission,
        )
    except ValidationError as exc:
        return JsonResponse({'error': '; '.join(exc.messages)}, status=400)

    return JsonResponse({
        'status': 'shared',
        'message': f'Shared with {recipient.email} as {share.get_permission_display()}.',
        'share': {
            'id': share.pk,
            'email': recipient.email,
            'username': recipient.username,
            'permission': share.permission,
            'permission_display': share.get_permission_display(),
            'update_url': reverse('documents:update_share', kwargs={'pk': document.pk, 'share_id': share.pk}),
            'revoke_url': reverse('documents:revoke_share', kwargs={'pk': document.pk, 'share_id': share.pk}),
        },
    }, status=201)


@login_required
@require_POST
def update_share(request, pk, share_id):
    """Update an existing collaborator's permission between viewer and editor."""
    document, error_response = _get_owned_document_or_json_error(pk, request.user)
    if error_response:
        return error_response

    try:
        share = DocumentShare.objects.select_related('user').get(pk=share_id, document=document)
    except DocumentShare.DoesNotExist:
        return JsonResponse({'error': 'Collaborator share not found.'}, status=404)

    data = _parse_request_payload(request)
    if data is None:
        return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)

    permission = (data.get('permission') or '').strip().lower()
    valid_permissions = {
        DocumentShare.Permission.VIEWER,
        DocumentShare.Permission.EDITOR,
    }
    if permission not in valid_permissions:
        return JsonResponse({'error': 'Invalid permission. Choose viewer or editor.'}, status=400)

    share.permission = permission
    share.save()

    return JsonResponse({
        'status': 'updated',
        'message': f'Updated {share.user.email or share.user.username} to {share.get_permission_display()}.',
        'share': {
            'id': share.pk,
            'permission': share.permission,
            'permission_display': share.get_permission_display(),
        },
    })


@login_required
@require_POST
def revoke_share(request, pk, share_id):
    """Revoke a collaborator's access to a document."""
    document, error_response = _get_owned_document_or_json_error(pk, request.user)
    if error_response:
        return error_response

    try:
        share = DocumentShare.objects.select_related('user').get(pk=share_id, document=document)
    except DocumentShare.DoesNotExist:
        return JsonResponse({'error': 'Collaborator share not found.'}, status=404)

    recipient_label = share.user.email or share.user.username
    share.delete()

    return JsonResponse({
        'status': 'revoked',
        'share_id': share_id,
        'message': f'Removed access for {recipient_label}.',
    })
