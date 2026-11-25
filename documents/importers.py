import html
import pathlib
import markdown
from .sanitizer import sanitize_html

MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB in bytes
ALLOWED_EXTENSIONS = {'.txt', '.md'}


class DocumentImportError(Exception):
    """Custom exception raised when file upload fails validation or parsing."""
    pass


def validate_and_process_upload(uploaded_file):
    """
    Validates uploaded file size, extension, and content encoding.
    Converts plain text or Markdown safely into sanitized HTML.
    Returns (title, sanitized_html).
    Raises DocumentImportError on any validation or parsing failure.
    """
    if not uploaded_file:
        raise DocumentImportError("No file was uploaded.")

    filename = uploaded_file.name or ''
    ext = pathlib.Path(filename).suffix.lower()

    # 1. Validate file extension
    if ext not in ALLOWED_EXTENSIONS:
        raise DocumentImportError(
            f"Unsupported file type '{ext or 'unknown'}'. Only .txt and .md files are supported."
        )

    # 2. Validate file size on uploaded_file attribute
    if uploaded_file.size > MAX_FILE_SIZE:
        raise DocumentImportError("File size exceeds the 2 MB limit.")

    # 3. Read raw content from memory and validate byte size
    raw_bytes = uploaded_file.read()
    if not raw_bytes or len(raw_bytes.strip()) == 0:
        raise DocumentImportError("The uploaded file is empty.")

    if len(raw_bytes) > MAX_FILE_SIZE:
        raise DocumentImportError("File size exceeds the 2 MB limit.")

    # 4. Validate UTF-8 decoding
    try:
        text_content = raw_bytes.decode('utf-8')
    except UnicodeDecodeError:
        raise DocumentImportError("File is not valid UTF-8 text.")

    if not text_content.strip():
        raise DocumentImportError("The uploaded file contains no readable text.")

    # 5. Extract and validate document title from filename
    raw_title = pathlib.Path(filename).stem.strip()
    title = raw_title if raw_title else 'Imported Document'
    if len(title) > 255:
        title = title[:255].strip()
    if not title:
        title = 'Imported Document'

    # 6. Convert file content to HTML based on extension
    if ext == '.txt':
        converted_html = _convert_txt_to_html(text_content)
    elif ext == '.md':
        converted_html = _convert_md_to_html(text_content)
    else:
        raise DocumentImportError(f"Unsupported file type: {ext}")

    # 7. Sanitize resulting HTML through the Draftly HTML sanitizer
    final_html = sanitize_html(converted_html)

    return title, final_html


def _convert_txt_to_html(text: str) -> str:
    """
    Converts plain text into readable HTML paragraphs while preserving line breaks.
    Escapes all HTML entities so user-provided text cannot execute as markup.
    """
    normalized = text.replace('\r\n', '\n').replace('\r', '\n').strip()
    if not normalized:
        return ''

    paragraphs = normalized.split('\n\n')
    html_paragraphs = []
    for para in paragraphs:
        lines = para.split('\n')
        escaped_lines = [html.escape(line) for line in lines]
        html_paragraphs.append('<p>' + '<br>'.join(escaped_lines) + '</p>')

    return ''.join(html_paragraphs)


def _convert_md_to_html(text: str) -> str:
    """
    Converts Markdown to HTML using python-markdown, supporting headings,
    bold, italic, links, lists, and linebreaks.
    """
    md_html = markdown.markdown(
        text,
        extensions=['extra', 'sane_lists', 'nl2br'],
    )
    return md_html
