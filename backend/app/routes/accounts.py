from fastapi import APIRouter, HTTPException

from ..schemas import AccountHistoryRequest, AccountLoginRequest
from ..services import accounts

router = APIRouter()


@router.post("/login")
def login(req: AccountLoginRequest):
    return accounts.open_account(req.username.strip())


@router.put("/{username}")
def save_account(username: str, req: AccountHistoryRequest):
    try:
        if not accounts.save_investigations(username, req.investigations):
            raise HTTPException(404, "Username not found. Sign in again to continue.")
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"ok": True}
