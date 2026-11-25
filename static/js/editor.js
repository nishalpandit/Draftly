// Editor Autosave and Quill setup
(function () {
    const configEl = document.getElementById('editor-config');
    if (!configEl) return;

    const saveUrl = configEl.getAttribute('data-save-url');
    const canEdit = configEl.getAttribute('data-can-edit') === 'true';
    const csrfToken = configEl.getAttribute('data-csrf-token');

    const titleInput = document.getElementById('document-title');
    const statusBadge = document.getElementById('save-status');
    const statusIcon = document.getElementById('save-status-icon');
    const statusText = document.getElementById('save-status-text');

    // Toolbar options
    const toolbarOptions = [
        [{ 'header': [1, 2, 3, false] }],
        ['bold', 'italic', 'underline', 'strike'],
        [{ 'color': [] }, { 'background': [] }],
        [{ 'list': 'ordered' }, { 'list': 'bullet' }],
        [{ 'align': [] }],
        ['link', 'clean']
    ];

    // Initialize Quill
    const quill = new Quill('#quill-editor', {
        theme: 'snow',
        readOnly: !canEdit,
        placeholder: 'Start writing your document...',
        modules: {
            toolbar: canEdit ? '#toolbar-container' : false
        }
    });

    // Populate initial content from server template
    const rawContentEl = document.getElementById('initial-content');
    if (rawContentEl && rawContentEl.innerHTML.trim()) {
        quill.clipboard.dangerouslyPasteHTML(rawContentEl.innerHTML);
    }

    if (!canEdit) {
        return; // Read-only view, no autosave required
    }

    let lastSavedTitle = titleInput ? titleInput.value.trim() : '';
    let lastSavedContent = quill.root.innerHTML;
    let saveTimeout = null;
    let isSaving = false;
    let pendingRetry = false;

    function setStatus(state, message) {
        if (!statusBadge || !statusIcon || !statusText) return;

        statusBadge.className = 'save-status-badge border';
        if (state === 'saving') {
            statusBadge.classList.add('bg-light', 'text-secondary');
            statusIcon.className = 'spinner-border spinner-border-sm text-primary';
            statusText.textContent = 'Saving...';
        } else if (state === 'saved') {
            statusBadge.classList.add('bg-white', 'text-secondary');
            statusIcon.className = 'bi bi-check2 text-success';
            statusText.textContent = message || 'Saved';
        } else if (state === 'failed') {
            statusBadge.classList.add('bg-danger-subtle', 'text-danger');
            statusIcon.className = 'bi bi-exclamation-triangle-fill text-danger';
            statusText.textContent = 'Save failed (click to retry)';
        }
    }

    async function executeSave() {
        if (isSaving) return;

        const currentTitle = titleInput ? titleInput.value.trim() : '';
        const currentContent = quill.root.innerHTML;

        // Skip unnecessary save requests when unchanged
        if (currentTitle === lastSavedTitle && currentContent === lastSavedContent) {
            return;
        }

        isSaving = true;
        setStatus('saving');

        try {
            const response = await fetch(saveUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    title: currentTitle || 'Untitled Document',
                    content: currentContent
                })
            });

            if (!response.ok) {
                throw new Error('Save response status: ' + response.status);
            }

            const data = await response.json();
            lastSavedTitle = currentTitle;
            lastSavedContent = currentContent;
            pendingRetry = false;

            // Update browser title
            if (currentTitle) {
                document.title = currentTitle + ' - Draftly';
            }

            const timeStr = data.updated_at ? 'Saved at ' + data.updated_at : 'Saved';
            setStatus('saved', timeStr);
        } catch (err) {
            console.error('Autosave error:', err);
            pendingRetry = true;
            setStatus('failed');
        } finally {
            isSaving = false;
        }
    }

    function triggerDebounce() {
        const currentTitle = titleInput ? titleInput.value.trim() : '';
        const currentContent = quill.root.innerHTML;

        if (currentTitle === lastSavedTitle && currentContent === lastSavedContent) {
            return;
        }

        if (statusText && statusText.textContent !== 'Saving...') {
            setStatus('saving');
        }

        if (saveTimeout) {
            clearTimeout(saveTimeout);
        }

        // Debounce ~1000ms
        saveTimeout = setTimeout(function () {
            executeSave();
        }, 1000);
    }

    // Listen to editor content changes
    quill.on('text-change', function (delta, oldDelta, source) {
        if (source === 'user') {
            triggerDebounce();
        }
    });

    // Listen to title changes
    if (titleInput) {
        titleInput.addEventListener('input', function () {
            triggerDebounce();
        });

        titleInput.addEventListener('blur', function () {
            // Save immediately on title blur if changed
            if (saveTimeout) clearTimeout(saveTimeout);
            executeSave();
        });
    }

    // Retry on status badge click if failed
    if (statusBadge) {
        statusBadge.addEventListener('click', function () {
            if (statusBadge.classList.contains('bg-danger-subtle')) {
                executeSave();
            }
        });
    }
})();

// Document Sharing Modal logic (Owner only)
(function () {
    const configEl = document.getElementById('editor-config');
    const shareForm = document.getElementById('share-document-form');
    if (!configEl || !shareForm) return;

    const csrfToken = configEl.getAttribute('data-csrf-token');
    const emailInput = document.getElementById('share-email-input');
    const permissionSelect = document.getElementById('share-permission-select');
    const submitBtn = document.getElementById('share-submit-btn');
    const submitSpinner = document.getElementById('share-submit-spinner');
    const submitText = document.getElementById('share-submit-text');
    const feedbackEl = document.getElementById('share-feedback');
    const collaboratorsList = document.getElementById('collaborators-list');
    const noCollaboratorsMsg = document.getElementById('no-collaborators-msg');

    function showFeedback(type, message) {
        if (!feedbackEl) return;
        feedbackEl.className = 'alert py-2 small mb-3';
        feedbackEl.classList.add(type === 'success' ? 'alert-success' : 'alert-danger');
        feedbackEl.textContent = message;
        feedbackEl.classList.remove('d-none');
    }

    function hideFeedback() {
        if (feedbackEl) {
            feedbackEl.classList.add('d-none');
            feedbackEl.textContent = '';
        }
    }

    function updateEmptyState() {
        if (!collaboratorsList || !noCollaboratorsMsg) return;
        const rows = collaboratorsList.querySelectorAll('.collaborator-row');
        if (rows.length === 0) {
            noCollaboratorsMsg.classList.remove('d-none');
        } else {
            noCollaboratorsMsg.classList.add('d-none');
        }
    }

    function createCollaboratorRow(share) {
        const row = document.createElement('div');
        row.className = 'list-group-item d-flex align-items-center justify-content-between gap-2 py-2 px-3 collaborator-row';
        row.setAttribute('data-share-id', share.id);

        const infoDiv = document.createElement('div');
        infoDiv.className = 'overflow-hidden me-auto';

        const primaryEl = document.createElement('div');
        primaryEl.className = 'small fw-semibold text-dark text-truncate';
        primaryEl.textContent = share.email || share.username;
        infoDiv.appendChild(primaryEl);

        if (share.email) {
            const subEl = document.createElement('div');
            subEl.className = 'text-muted';
            subEl.style.fontSize = '0.75rem';
            subEl.textContent = '@' + share.username;
            infoDiv.appendChild(subEl);
        }

        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'd-flex align-items-center gap-2 flex-shrink-0';

        const select = document.createElement('select');
        select.className = 'form-select form-select-sm collaborator-role-select';
        select.style.width = 'auto';
        select.setAttribute('data-update-url', share.update_url);
        select.setAttribute('data-current-role', share.permission);
        select.setAttribute('aria-label', 'Change role for ' + (share.email || share.username));

        const viewerOpt = document.createElement('option');
        viewerOpt.value = 'viewer';
        viewerOpt.textContent = 'Viewer';
        if (share.permission === 'viewer') viewerOpt.selected = true;

        const editorOpt = document.createElement('option');
        editorOpt.value = 'editor';
        editorOpt.textContent = 'Editor';
        if (share.permission === 'editor') editorOpt.selected = true;

        select.appendChild(viewerOpt);
        select.appendChild(editorOpt);

        const revokeBtn = document.createElement('button');
        revokeBtn.type = 'button';
        revokeBtn.className = 'btn btn-outline-danger btn-sm collaborator-revoke-btn';
        revokeBtn.setAttribute('data-revoke-url', share.revoke_url);
        revokeBtn.title = 'Revoke access';
        revokeBtn.innerHTML = '<i class="bi bi-trash"></i>';

        actionsDiv.appendChild(select);
        actionsDiv.appendChild(revokeBtn);

        row.appendChild(infoDiv);
        row.appendChild(actionsDiv);
        return row;
    }

    shareForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        hideFeedback();

        const email = emailInput ? emailInput.value.trim() : '';
        const permission = permissionSelect ? permissionSelect.value : 'viewer';
        if (!email) {
            showFeedback('error', 'Please enter an email address.');
            return;
        }

        if (submitBtn) submitBtn.disabled = true;
        if (submitSpinner) submitSpinner.classList.remove('d-none');
        if (submitText) submitText.textContent = 'Sharing...';

        try {
            const response = await fetch(shareForm.action, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ email: email, permission: permission })
            });

            const data = await response.json();
            if (!response.ok) {
                showFeedback('error', data.error || 'Could not share document.');
                return;
            }

            if (data.share && collaboratorsList) {
                const newRow = createCollaboratorRow(data.share);
                if (noCollaboratorsMsg) {
                    collaboratorsList.insertBefore(newRow, noCollaboratorsMsg);
                } else {
                    collaboratorsList.appendChild(newRow);
                }
                updateEmptyState();
            }

            if (emailInput) emailInput.value = '';
            showFeedback('success', data.message || 'Document shared successfully.');
        } catch (err) {
            console.error('Share error:', err);
            showFeedback('error', 'Network error while sharing document. Please try again.');
        } finally {
            if (submitBtn) submitBtn.disabled = false;
            if (submitSpinner) submitSpinner.classList.add('d-none');
            if (submitText) submitText.textContent = 'Share';
        }
    });

    if (collaboratorsList) {
        collaboratorsList.addEventListener('change', async function (e) {
            const select = e.target.closest('.collaborator-role-select');
            if (!select) return;

            hideFeedback();
            const updateUrl = select.getAttribute('data-update-url');
            const previousRole = select.getAttribute('data-current-role');
            const newRole = select.value;

            select.disabled = true;
            try {
                const response = await fetch(updateUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify({ permission: newRole })
                });

                const data = await response.json();
                if (!response.ok) {
                    select.value = previousRole;
                    showFeedback('error', data.error || 'Could not update role.');
                    return;
                }

                select.setAttribute('data-current-role', newRole);
                showFeedback('success', data.message || 'Role updated.');
            } catch (err) {
                console.error('Update role error:', err);
                select.value = previousRole;
                showFeedback('error', 'Network error while updating role.');
            } finally {
                select.disabled = false;
            }
        });

        collaboratorsList.addEventListener('click', async function (e) {
            const revokeBtn = e.target.closest('.collaborator-revoke-btn');
            if (!revokeBtn) return;

            hideFeedback();
            const revokeUrl = revokeBtn.getAttribute('data-revoke-url');
            const row = revokeBtn.closest('.collaborator-row');

            revokeBtn.disabled = true;
            try {
                const response = await fetch(revokeUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    }
                });

                const data = await response.json();
                if (!response.ok) {
                    revokeBtn.disabled = false;
                    showFeedback('error', data.error || 'Could not revoke access.');
                    return;
                }

                if (row) row.remove();
                updateEmptyState();
                showFeedback('success', data.message || 'Access revoked.');
            } catch (err) {
                console.error('Revoke error:', err);
                revokeBtn.disabled = false;
                showFeedback('error', 'Network error while revoking access.');
            }
        });
    }
})();
