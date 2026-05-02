from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from ..dependencies import get_current_user
from ..models import User, UserRole
from ..templating import templates

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
def index(request: Request, user: User | None = Depends(get_current_user)):
    return templates.TemplateResponse(request, "index.html", {"user": user})


@router.get("/account", response_class=HTMLResponse)
def buyer_account(request: Request, user: User | None = Depends(get_current_user)):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    if user.role != UserRole.BUYER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ только для покупателей.")
    return templates.TemplateResponse(request, "buyer.html", {"user": user})



