"""Integration tests for the POST /extract endpoint required by the load-testing TP."""
from fastapi.testclient import TestClient

from app.main import app

EXTRACT_PATH = "/extract"

client = TestClient(app)


def _upload(content: bytes):
    return client.post(
        EXTRACT_PATH,
        files={"file": ("doc.pdf", content, "application/pdf")},
    )


def _send_raw(content: bytes, content_type: str):
    return client.post(EXTRACT_PATH, content=content, headers={"Content-Type": content_type})


class TestExtractSuccess:
    def test_returns_content_and_page_count(self, small_pdf_bytes):
        response = _upload(small_pdf_bytes)

        assert response.status_code == 200
        body = response.json()
        assert "Page 1" in body["content"]
        assert body["page_count"] == 1

    def test_response_only_has_the_tp_fields(self, small_pdf_bytes):
        response = _upload(small_pdf_bytes)

        assert set(response.json()) == {"content", "page_count"}

    def test_counts_every_page_of_a_large_pdf(self, large_pdf_bytes):
        response = _upload(large_pdf_bytes)

        assert response.status_code == 200
        assert response.json()["page_count"] == 100


class TestExtractRawBody:
    """The TP allows sending the PDF as the raw request body instead of multipart."""

    def test_extracts_pdf_sent_as_raw_body(self, small_pdf_bytes):
        response = _send_raw(small_pdf_bytes, "application/pdf")

        assert response.status_code == 200
        assert "Page 1" in response.json()["content"]
        assert response.json()["page_count"] == 1

    def test_accepts_raw_body_with_generic_binary_content_type(self, small_pdf_bytes):
        response = _send_raw(small_pdf_bytes, "application/octet-stream")

        assert response.status_code == 200
        assert response.json()["page_count"] == 1

    def test_rejects_corrupted_pdf_sent_as_raw_body(self, corrupted_pdf_bytes):
        response = _send_raw(corrupted_pdf_bytes, "application/pdf")

        assert response.status_code == 422
        assert response.json()["detail"].startswith("No se pudo leer el archivo como PDF")


class TestExtractErrors:
    def test_rejects_corrupted_pdf(self, corrupted_pdf_bytes):
        response = _upload(corrupted_pdf_bytes)

        assert response.status_code == 422

    def test_rejects_multipart_without_file_field(self, small_pdf_bytes):
        response = client.post(EXTRACT_PATH, files={"otro": ("doc.pdf", small_pdf_bytes, "application/pdf")})

        assert response.status_code == 422
        assert response.json()["detail"].startswith("No se pudo leer el archivo como PDF")
