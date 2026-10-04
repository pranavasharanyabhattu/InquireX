import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import chunking, answer, accounts, vectorstore, extract
from app import config

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "llm_configured" in data
    assert "provider" in data
    assert "model" in data
    assert "ocr_available" in data


def test_chunking_pages():
    pages = [(1, "one two three four five six seven eight nine ten")]
    chunks = chunking.chunk_pages(pages)
    assert len(chunks) == 1
    assert chunks[0][0] == 1
    assert "one" in chunks[0][1]


def test_chunking_empty():
    assert chunking.chunk_pages([]) == []


def test_source_only_summary_extraction():
    passages = [
        {"doc_id": "doc1", "doc_name": "report.pdf", "page": 1, "text": "First sentence. Second sentence. Third."},
        {"doc_id": "doc2", "doc_name": "memo.txt", "page": 1, "text": "Notice regarding policy. Please read."},
    ]
    summary, citations = answer._source_only_summary(passages)
    assert "report.pdf" in summary
    assert "memo.txt" in summary
    assert len(citations) == 2


def test_generate_fallback_when_no_llm():
    passages = [
        {"doc_id": "doc1", "doc_name": "doc.pdf", "page": 1, "text": "The project launch date is June 15."}
    ]
    result = answer.generate("What is the launch date?", passages)
    assert "answer" in result
    assert result["confidence"] in {"high", "medium", "low"}
    assert len(result["used"]) >= 1


def test_accounts_open_and_save(tmp_path, monkeypatch):
    test_file = tmp_path / "test_accounts.json"
    monkeypatch.setattr(accounts, "_FILE", test_file)

    res = accounts.open_account("test_user")
    assert res["username"] == "test_user"
    assert res["created"] is True
    assert res["investigations"] == []

    # Opening existing account returns created=False
    res2 = accounts.open_account("test_user")
    assert res2["created"] is False

    # Save investigations
    inv = [{"id": "inv-123", "title": "My search", "documentIds": ["d1"], "turns": []}]
    saved = accounts.save_investigations("test_user", inv)
    assert saved is True

    # Re-open account and check persisted data
    res3 = accounts.open_account("test_user")
    assert len(res3["investigations"]) == 1
    assert res3["investigations"][0]["id"] == "inv-123"


def test_vectorstore_empty_add_chunks():
    # Should not raise exception when empty chunks passed
    vectorstore.add_chunks("doc-empty", "empty.pdf", [])


def test_login_validation():
    # Username with invalid characters should fail validation
    res = client.post("/api/accounts/login", json={"username": "ab"})
    assert res.status_code == 422

    res_invalid_chars = client.post("/api/accounts/login", json={"username": "user!@#$"})
    assert res_invalid_chars.status_code == 422

    # Valid username succeeds
    res_valid = client.post("/api/accounts/login", json={"username": "valid_user_123"})
    assert res_valid.status_code == 200


def test_search_endpoint():
    res = client.post("/api/search", json={"query": "test query", "document_ids": []})
    assert res.status_code == 200
    data = res.json()
    assert data["query"] == "test query"
    assert isinstance(data["results"], list)


def test_delete_invalid_doc_id():
    res = client.delete("/api/documents/invalid..id")
    assert res.status_code == 400


def test_extract_empty_txt(tmp_path):
    empty_file = tmp_path / "empty.txt"
    empty_file.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        extract.extract_pages(empty_file)

