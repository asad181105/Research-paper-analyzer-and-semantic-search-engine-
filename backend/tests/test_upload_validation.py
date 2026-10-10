from io import BytesIO

from werkzeug.datastructures import FileStorage

from app.services.ingest import validate_upload


def test_reject_non_pdf():
    fs = FileStorage(stream=BytesIO(b"hello"), filename="a.txt", content_type="text/plain")
    try:
        validate_upload(fs, 25)
        assert False, "should have raised"
    except ValueError:
        pass


def test_reject_bad_header():
    fs = FileStorage(
        stream=BytesIO(b"xxxxx" + b"0" * 100),
        filename="a.pdf",
        content_type="application/pdf",
    )
    try:
        validate_upload(fs, 25)
        assert False
    except ValueError as e:
        assert "valid PDF" in str(e)


def test_accept_pdf_header():
    fs = FileStorage(
        stream=BytesIO(b"%PDF-1.4 " + b"0" * 100),
        filename="ok.pdf",
        content_type="application/pdf",
    )
    validate_upload(fs, 25)
