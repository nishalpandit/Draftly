// Dashboard client-side search and interaction logic
document.addEventListener('DOMContentLoaded', function () {
    const searchInput = document.getElementById('doc-search');
    const ownedCards = document.querySelectorAll('.owned-doc-card');
    const sharedCards = document.querySelectorAll('.shared-doc-card');
    const ownedEmptySearch = document.getElementById('owned-empty-search');
    const sharedEmptySearch = document.getElementById('shared-empty-search');

    if (searchInput) {
        searchInput.addEventListener('input', function (e) {
            const query = e.target.value.trim().toLowerCase();

            let visibleOwned = 0;
            ownedCards.forEach(function (card) {
                const title = (card.getAttribute('data-title') || '').toLowerCase();
                if (title.includes(query)) {
                    card.classList.remove('d-none');
                    visibleOwned++;
                } else {
                    card.classList.add('d-none');
                }
            });

            if (ownedEmptySearch) {
                if (visibleOwned === 0 && ownedCards.length > 0) {
                    ownedEmptySearch.classList.remove('d-none');
                } else {
                    ownedEmptySearch.classList.add('d-none');
                }
            }

            let visibleShared = 0;
            sharedCards.forEach(function (card) {
                const title = (card.getAttribute('data-title') || '').toLowerCase();
                if (title.includes(query)) {
                    card.classList.remove('d-none');
                    visibleShared++;
                } else {
                    card.classList.add('d-none');
                }
            });

            if (sharedEmptySearch) {
                if (visibleShared === 0 && sharedCards.length > 0) {
                    sharedEmptySearch.classList.remove('d-none');
                } else {
                    sharedEmptySearch.classList.add('d-none');
                }
            }
        });
    }

    // Mobile sidebar toggle
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const sidebar = document.querySelector('.dashboard-sidebar');
    const overlay = document.querySelector('.sidebar-overlay');

    if (sidebarToggle && sidebar && overlay) {
        sidebarToggle.addEventListener('click', function () {
            sidebar.classList.toggle('show');
            overlay.classList.toggle('show');
        });

        overlay.addEventListener('click', function () {
            sidebar.classList.remove('show');
            overlay.classList.remove('show');
        });
    }

    // Delete confirmation modal setup
    const deleteModal = document.getElementById('deleteConfirmModal');
    if (deleteModal) {
        deleteModal.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            const docId = button.getAttribute('data-doc-id');
            const docTitle = button.getAttribute('data-doc-title');
            const deleteUrl = button.getAttribute('data-delete-url');

            const titlePlaceholder = deleteModal.querySelector('#delete-modal-doc-title');
            const form = deleteModal.querySelector('#delete-doc-form');

            if (titlePlaceholder) {
                titlePlaceholder.textContent = docTitle || 'this document';
            }
            if (form) {
                form.action = deleteUrl;
            }
        });
    }

    // Import modal file handling and validation
    const modalFileInput = document.getElementById('modal-file-input');
    const modalDropzone = document.getElementById('modal-dropzone');
    const modalPreview = document.getElementById('modal-file-preview');
    const modalName = document.getElementById('modal-file-name');
    const modalSize = document.getElementById('modal-file-size');
    const modalClear = document.getElementById('modal-file-clear');
    const modalSubmit = document.getElementById('modal-import-submit-btn');
    const modalError = document.getElementById('modal-validation-error');
    const modalForm = document.getElementById('modal-import-form');
    const modalSpinner = document.getElementById('modal-import-spinner');
    const modalBtnText = document.getElementById('modal-import-btn-text');

    const MAX_SIZE = 2 * 1024 * 1024; // 2 MB
    const ALLOWED_EXTS = ['.txt', '.md'];

    function handleModalFile(file) {
        if (!modalError || !modalPreview || !modalSubmit) return;

        modalError.classList.add('d-none');
        modalError.textContent = '';

        if (!file) {
            modalPreview.classList.add('d-none');
            modalSubmit.disabled = true;
            return;
        }

        const ext = '.' + file.name.split('.').pop().toLowerCase();
        if (!ALLOWED_EXTS.includes(ext)) {
            modalError.textContent = 'Invalid file type: ' + ext + '. Only .txt and .md files are supported.';
            modalError.classList.remove('d-none');
            modalPreview.classList.add('d-none');
            modalSubmit.disabled = true;
            modalFileInput.value = '';
            return;
        }

        if (file.size > MAX_SIZE) {
            modalError.textContent = 'File exceeds maximum limit of 2 MB (' + (file.size / (1024 * 1024)).toFixed(2) + ' MB).';
            modalError.classList.remove('d-none');
            modalPreview.classList.add('d-none');
            modalSubmit.disabled = true;
            modalFileInput.value = '';
            return;
        }

        if (file.size === 0) {
            modalError.textContent = 'The selected file is empty.';
            modalError.classList.remove('d-none');
            modalPreview.classList.add('d-none');
            modalSubmit.disabled = true;
            modalFileInput.value = '';
            return;
        }

        modalName.textContent = file.name;
        modalSize.textContent = (file.size / 1024).toFixed(1) + ' KB';
        modalPreview.classList.remove('d-none');
        modalSubmit.disabled = false;
    }

    if (modalFileInput) {
        modalFileInput.addEventListener('change', function () {
            if (modalFileInput.files.length > 0) {
                handleModalFile(modalFileInput.files[0]);
            }
        });
    }

    if (modalClear && modalFileInput) {
        modalClear.addEventListener('click', function () {
            modalFileInput.value = '';
            handleModalFile(null);
        });
    }

    if (modalDropzone && modalFileInput) {
        ['dragenter', 'dragover'].forEach(function (name) {
            modalDropzone.addEventListener(name, function (e) {
                e.preventDefault();
                e.stopPropagation();
                modalDropzone.classList.add('dragover');
            });
        });

        ['dragleave', 'drop'].forEach(function (name) {
            modalDropzone.addEventListener(name, function (e) {
                e.preventDefault();
                e.stopPropagation();
                modalDropzone.classList.remove('dragover');
            });
        });

        modalDropzone.addEventListener('drop', function (e) {
            if (e.dataTransfer && e.dataTransfer.files.length > 0) {
                modalFileInput.files = e.dataTransfer.files;
                handleModalFile(modalFileInput.files[0]);
            }
        });
    }

    if (modalForm && modalSubmit && modalSpinner && modalBtnText) {
        modalForm.addEventListener('submit', function () {
            modalSubmit.disabled = true;
            modalSpinner.classList.remove('d-none');
            modalBtnText.textContent = 'Importing...';
        });
    }
});
