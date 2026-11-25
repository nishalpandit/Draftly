import bleach

ALLOWED_TAGS = [
    'p', 'br', 'span', 'strong', 'b', 'em', 'i', 'u', 's', 'strike',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'blockquote', 'pre', 'code',
    'ul', 'ol', 'li',
    'a', 'sub', 'sup'
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target', 'rel'],
    'span': ['class', 'style'],
    'p': ['class', 'style'],
    'h1': ['class', 'style'],
    'h2': ['class', 'style'],
    'h3': ['class', 'style'],
    'h4': ['class', 'style'],
    'h5': ['class', 'style'],
    'h6': ['class', 'style'],
    'li': ['class', 'data-list'],
    'pre': ['class'],
    'code': ['class'],
}

ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']

ALLOWED_CSS_PROPERTIES = [
    'color', 'background-color', 'text-align'
]

try:
    from bleach.css_sanitizer import CSSSanitizer
    css_sanitizer = CSSSanitizer(allowed_css_properties=ALLOWED_CSS_PROPERTIES)
except (ImportError, ModuleNotFoundError):
    css_sanitizer = None


def sanitize_html(html_content: str) -> str:
    """
    Sanitize user-provided HTML content to prevent XSS vulnerabilities,
    allowing only safe semantic elements, attributes, and styles used by Quill.
    Falls back gracefully if CSSSanitizer is unavailable.
    """
    if not html_content:
        return ''

    clean_kwargs = {
        'tags': ALLOWED_TAGS,
        'attributes': ALLOWED_ATTRIBUTES,
        'protocols': ALLOWED_PROTOCOLS,
        'strip': True,
    }
    if css_sanitizer is not None:
        clean_kwargs['css_sanitizer'] = css_sanitizer

    return bleach.clean(html_content, **clean_kwargs)


# Alias
sanitize_document_html = sanitize_html
