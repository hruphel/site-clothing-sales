from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models import ROLE_LABELS_RU, User, UserRole
from ..security import hash_password, verify_password
from ..templating import templates

router = APIRouter(tags=["auth"])

ALLOWED_REGISTER_ROLES = {UserRole.BUYER, UserRole.SELLER}


def _redirect_for_role(user: User) -> RedirectResponse:
    if user.role == UserRole.ADMIN:
        target = "/admin"
    elif user.role == UserRole.SELLER:
        target = "/seller"
    else:
        target = "/account"
    return RedirectResponse(url=target, status_code=303)


@router.get("/register", response_class=HTMLResponse)
def register_form(
    request: Request,
    user: User | None = Depends(get_current_user),
):
    if user is not None:
        return _redirect_for_role(user)
    return templates.TemplateResponse(
        request,
        "register.html",
        {
            "errors": [],
            "form": {"username": "", "email": "", "role": UserRole.BUYER.value},
            "user": None,
            "roles": [
                (UserRole.BUYER.value, ROLE_LABELS_RU[UserRole.BUYER]),
                (UserRole.SELLER.value, ROLE_LABELS_RU[UserRole.SELLER]),
            ],
        },
    )


@router.post("/register", response_class=HTMLResponse)
def register_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    role: str = Form(UserRole.BUYER.value),
    db: Session = Depends(get_db),
):
    errors: list[str] = []
    username = username.strip()
    email = email.strip().lower()

    if len(username) < 3 or len(username) > 64:
        errors.append("Логин должен быть от 3 до 64 символов.")
    try:
        email = validate_email(email, check_deliverability=False).normalized
    except EmailNotValidError:
        errors.append("Введите корректный email.")
    if len(password) < 6:
        errors.append("Пароль должен быть не короче 6 символов.")
    if password != password_confirm:
        errors.append("Пароли не совпадают.")

    try:
        role_enum = UserRole(role)
    except ValueError:
        role_enum = UserRole.BUYER
    if role_enum not in ALLOWED_REGISTER_ROLES:
        errors.append("Регистрация администратора через форму недоступна.")
        role_enum = UserRole.BUYER

    if not errors:
        existing = (
            db.query(User)
            .filter(or_(User.username == username, User.email == email))
            .first()
        )
        if existing is not None:
            if existing.username == username:
                errors.append("Логин уже используется.")
            if existing.email == email:
                errors.append("Email уже используется.")

    if errors:
        return templates.TemplateResponse(
            request,
            "register.html",
            {
                "errors": errors,
                "form": {"username": username, "email": email, "role": role_enum.value},
                "user": None,
                "roles": [
                    (UserRole.BUYER.value, ROLE_LABELS_RU[UserRole.BUYER]),
                    (UserRole.SELLER.value, ROLE_LABELS_RU[UserRole.SELLER]),
                ],
            },
            status_code=400,
        )

    new_user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        role=role_enum,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    request.session["user_id"] = new_user.id
    return _redirect_for_role(new_user)


@router.get("/login", response_class=HTMLResponse)
def login_form(
    request: Request,
    user: User | None = Depends(get_current_user),
):
    if user is not None:
        return _redirect_for_role(user)
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "errors": [],
            "form": {"identifier": ""},
            "user": None,
        },
    )


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    identifier: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    errors: list[str] = []
    identifier_clean = identifier.strip()
    candidate = (
        db.query(User)
        .filter(
            or_(
                User.username == identifier_clean,
                User.email == identifier_clean.lower(),
            )
        )
        .first()
    )
    if candidate is None or not verify_password(password, candidate.password_hash):
        errors.append("Неверный логин/email или пароль.")

    if errors:
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "errors": errors,
                "form": {"identifier": identifier_clean},
                "user": None,
            },
            status_code=400,
        )

    assert candidate is not None
    request.session["user_id"] = candidate.id
    return _redirect_for_role(candidate)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)
