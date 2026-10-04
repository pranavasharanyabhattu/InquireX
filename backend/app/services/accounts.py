"""Simple local username registry with persistent investigation histories.

This is intended for a local/demo workspace. Usernames are identifiers, not
credentials; deployments that need privacy should add real authentication.
"""
import json
from threading import Lock

from .. import config

_lock = Lock()
_FILE = config.DATA_DIR / "accounts.json"


def _read() -> dict:
    if not _FILE.exists():
        return {}
    try:
        data = json.loads(_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("The account registry could not be read; it was left unchanged.") from exc
    if not isinstance(data, dict):
        raise RuntimeError("The account registry has an invalid format; it was left unchanged.")
    return data


def _write(data: dict) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp = _FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    temp.replace(_FILE)


def _remove_duplicate_investigations(data: dict) -> bool:
    """Keep investigation and document IDs private to their first account."""
    owners: dict[str, str] = {}
    document_owners: dict[str, str] = {}
    changed = False
    for username_key, account in data.items():
        if not isinstance(account, dict):
            continue
        kept = []
        for investigation in account.get("investigations", []):
            investigation_id = investigation.get("id") if isinstance(investigation, dict) else None
            owner = owners.get(investigation_id) if investigation_id else None
            if owner and owner != username_key:
                changed = True
                continue
            if investigation_id:
                owners.setdefault(investigation_id, username_key)
            if isinstance(investigation, dict):
                original_docs = investigation.get("documentIds", [])
                if isinstance(original_docs, list):
                    private_docs = [doc_id for doc_id in original_docs if document_owners.get(doc_id, username_key) == username_key]
                    for doc_id in private_docs:
                        document_owners.setdefault(doc_id, username_key)
                    if private_docs != original_docs:
                        investigation["documentIds"] = private_docs
                        changed = True
            kept.append(investigation)
        if len(kept) != len(account.get("investigations", [])):
            account["investigations"] = kept
    return changed


def open_account(username: str) -> dict:
    key = username.casefold()
    with _lock:
        data = _read()
        cleaned = _remove_duplicate_investigations(data)
        account = data.get(key)
        created = not isinstance(account, dict)
        if created:
            account = {"username": username, "investigations": []}
            data[key] = account
            cleaned = True
        if cleaned:
            _write(data)
        return {"username": account.get("username", username), "created": created, "investigations": account.get("investigations", [])}


def save_investigations(username: str, investigations: list[dict]) -> bool:
    key = username.casefold()
    with _lock:
        data = _read()
        if key not in data or not isinstance(data[key], dict):
            return False
        other_ids = {
            investigation.get("id")
            for other_key, account in data.items() if other_key != key and isinstance(account, dict)
            for investigation in account.get("investigations", [])
            if isinstance(investigation, dict) and investigation.get("id")
        }
        if any(isinstance(item, dict) and item.get("id") in other_ids for item in investigations):
            raise ValueError("An investigation cannot be saved into more than one username account.")
        data[key]["investigations"] = investigations
        _write(data)
        return True
