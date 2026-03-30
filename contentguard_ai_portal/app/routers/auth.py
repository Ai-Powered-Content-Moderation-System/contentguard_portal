# app/routers/auth.py

from fastapi import APIRouter, Request, Form, Depends, HTTPException, status
# from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
import bcrypt
import jwt
from datetime import datetime, timedelta
import secrets
import string

# Change this import - remove User from database import
from app.models.database import get_db, Notification

# Add this import for User
# from app.models.user import User
from app.models.database import User
from app.config import settings
from app.utils.helpers import create_access_token, get_password_hash, verify_password, notify_admins

router = APIRouter()
# templates = Jinja2Templates(directory="app/templates")
# app/routers/auth.py
from app.template import templates
# Remove any local Jinja2Templates initialization
def generate_username(name: str) -> str:
    """Generate unique username from name"""
    first_name = name.split()[0].lower()
    random_str = ''.join(secrets.choice(string.ascii_lowercase) for _ in range(6))
    random_num = str(secrets.randbelow(1000)).zfill(3)
    return f"{first_name}.{random_str}{random_num}"

def generate_password(length=8) -> str:
    """Generate random password"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    # Find user
    user = db.query(User).filter(User.username == username).first()

    if user and verify_password(password, user.password):
        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()

        # Create session token
        access_token = create_access_token(
            data={"sub": user.username, "is_admin": user.is_admin}
        )

        if not user.is_admin:
            notify_admins(db, f"User['{user.username}']logged in at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}.")

        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            httponly=True,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            secure=getattr(settings, 'SESSION_COOKIE_SECURE', False),
            samesite="lax"
        )
        return response

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Invalid username or password"}
    )

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register")
async def register(
    request: Request,
    name: str = Form(...),
    db: Session = Depends(get_db)
):
    # Generate credentials
    username = generate_username(name)
    email = f"{username}@contentguardai.com"
    password = generate_password()
    hashed = get_password_hash(password)

    # Create user
    user = User(
        username=username,
        email=email,
        password=hashed,
        name=name,
        is_admin=False
    )

    try:
        db.add(user)
        db.commit()
        notify_admins(db, f"New user registered: {user.username} ({user.name})")
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "username": username,
                
                "password": password,
                "success": True
            }
        )
    except Exception as e:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": f"Registration failed: {str(e)}"}
        )

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie("access_token")
    return response

@router.get("/forgot", response_class=HTMLResponse)
async def forgot_page(request: Request):
    return templates.TemplateResponse("forgot.html", {"request": request})

@router.post("/forgot")
async def forgot(
    request: Request,
    name: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.name == name).first()

    if user:
        return templates.TemplateResponse(
            "forgot.html",
            {
                "request": request,
                "message": f"Your username is: {user.username}. Password reset requires admin assistance."
            }
        )

    return templates.TemplateResponse(
        "forgot.html",
        {"request": request, "error": "No user found with that name"}
    )

# @router.post("/reset-password")
# async def reset_password(
#     request: Request,
#     username: str = Form(...),
#     new_password: str = Form(...),
#     db: Session = Depends(get_db)
# ):
#     user = db.query(User).filter(User.username == username).first()

#     if user:
#         user.password = get_password_hash(new_password)
#         db.commit()

#         return templates.TemplateResponse(
#             "forgot.html",
#             {"request": request, "reset_message": "Password reset successful!"}
#         )

#     return templates.TemplateResponse(
#         "forgot.html",
#         {"request": request, "reset_error": "Username not found"}
#     )

# ... existing imports ...

# Define a set of usernames that cannot reset password via this form
RESTRICTED_RESET_USERS = {"Admin", "Test", "Manas", "Suraj"}

@router.post("/reset-password")
async def reset_password(
    request: Request,
    username: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()

    if user:
        # Check if this user is in the restricted list
        if user.username in RESTRICTED_RESET_USERS:
            return templates.TemplateResponse(
                "forgot.html",
                {
                    "request": request,
                    "reset_error": f"Password reset for '{user.username}' is not allowed via this form. Please contact the system administrator."
                }
            )

        user.password = get_password_hash(new_password)
        db.commit()
        return templates.TemplateResponse(
            "forgot.html",
            {"request": request, "reset_message": "Password reset successful!"}
        )

    return templates.TemplateResponse(
        "forgot.html",
        {"request": request, "reset_error": "Username not found"}
    )

@router.post("/switch-theme")
async def switch_theme(
    request: Request,
    db: Session = Depends(get_db)
):
    """Switch user theme preference"""
    # Get user from token
    from app.utils.helpers import get_current_user_optional
    user = await get_current_user_optional(request, db)

    if user:
        # Toggle theme
        user.theme_preference = 'old' if user.theme_preference == 'modern' else 'modern'
        db.commit()

    # Redirect back
    referer = request.headers.get("referer", "/dashboard")
    return RedirectResponse(url=referer, status_code=302)