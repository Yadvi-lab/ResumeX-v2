# pdf_parser.py
"""Extracts plain text from an uploaded PDF resume."""
import pdfplumber

MAX_PAGES = 10  # a resume longer than this is almost certainly the wrong file


def extract_text_from_pdf(uploaded_file) -> str:
    """Return the text of a PDF (file path or file-like object).

    Raises:
        ValueError: if the file is not a readable PDF or is too long.
    """
    pages_text = []
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            if len(pdf.pages) > MAX_PAGES:
                raise ValueError(
                    f"The PDF has {len(pdf.pages)} pages. Upload a resume of "
                    f"{MAX_PAGES} pages or fewer."
                )
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)
    except ValueError:
        raise
    except Exception as exc:  # corrupted / encrypted / not a PDF
        raise ValueError(f"Could not read this PDF ({type(exc).__name__}).") from exc

    return "\n".join(pages_text).strip()
