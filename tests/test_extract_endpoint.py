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


class TestExtractErrors:
    def test_rejects_corrupted_pdf(self, corrupted_pdf_bytes):
        response = _upload(corrupted_pdf_bytes)

        assert response.status_code == 422
