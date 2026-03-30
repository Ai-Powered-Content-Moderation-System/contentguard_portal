# app/main.py - Update startup event

from fastapi import FastAPI, Request, Depends, HTTPException, status
# from fastapi.templating import Jinja2Templates
from app.template import templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from datetime import datetime, timedelta
from typing import Optional

from app.config import settings
from app.models.database import init_db,get_db
from app.models.database import User
# from app.models.user import init_mysql_tables
from app.models.extraction import init_extraction_tables  # Add this import
from app.routers import auth, admin, comments, classification, extraction
from app.services.classifier import classifier
from app.utils.helpers import get_current_user, create_admin_user, create_test_user,create_Suraj_user,create_Manas_user

from app.models.database import init_db, engine, User
from sqlalchemy import inspect

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


# from app.config import BASE_DIR
# Initialize app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG
)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    print("=== Validation Error ===")
    print(exc.errors())
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )
from pathlib import Path
# from fastapi.templating import Jinja2Templates
# Setup templates
# templates = Jinja2Templates(directory="app/templates")
from pathlib import Path

# BASE_DIR = Path(__file__).resolve().parent
# templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
# BASE_DIR = Path(__file__).resolve().parent
# TEMPLATES_DIR = BASE_DIR / "templates"

# templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
# Mount static files
import os
from fastapi.staticfiles import StaticFiles

# ... other imports ...
from fastapi.exceptions import RequestValidationError
from fastapi.responses import PlainTextResponse
# Get the absolute path to the static directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()
check_admin_4 = ""
check_admin_6 = ""
check_admin_5 = ""
#debug
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# init_db()
check_admin_1 = ""
check_admin_2 = ""
check_admin_3 = ""
 # Initialize the accumulator string
from app.routers import notifications
app.include_router(notifications.router, prefix="/api", tags=["notifications"])

from app.routers import dashboard
app.include_router(dashboard.router)

# Initialize SQLite base tables
try:
    init_db()
    check_admin_1+= "database initialized, "
except Exception as e:
    check_admin_1 += f"fail to database initialized: {e}, "

# Initialize extraction tables
try:
    init_extraction_tables()
    check_admin_2 += "extraction tables initialized, "
except Exception as e:
    check_admin_2 += f"fail to extraction tables initialized: {e}, "

# Create admin user
try:
    create_admin_user()
    
    check_admin_3 += "admin and test user created, "
except Exception as e:
    check_admin_3 += f"fail to admin creation: {e}, "
try:
    create_test_user()
    check_admin_4 += "admin and test user created, "
except Exception as e:
    check_admin_4 += f"fail to admin creation: {e}, "

try:
    create_Suraj_user()
    check_admin_5 += "admin and test user created, "
except Exception as e:
    check_admin_5 += f"fail to admin creation: {e}, "

try: 
    create_Manas_user()
    check_admin_6 += "admin and test user created, "
except Exception as e:
    check_admin_6 += f"fail to admin creation: {e}, "


# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(comments.router, prefix="/comments", tags=["Comments"])
app.include_router(classification.router, prefix="/classify", tags=["Classification"])
app.include_router(extraction.router, prefix="/extract", tags=["Extraction"])

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)



import logging
logging.basicConfig(filename='/home/contentguardai/contentguardportal_v2/fastapi_debug.log', level=logging.DEBUG)
# Root route
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    logger.debug(" route called 1")
    return templates.TemplateResponse(
        "login.html",
        {"request": request}
    )



# Dashboard route
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    page: int = 1,
    filter_level1: Optional[str] = None,
    filter_level2: Optional[str] = None,
    user = Depends(get_current_user)
):
    logger.debug(" route called 2")
    db = next(get_db())

    # Build query with filters
    from app.models.database import Comment
    query = db.query(Comment)
    if filter_level1:
        query = query.filter(Comment.level1_category == filter_level1)
    if filter_level2:
        query = query.filter(Comment.level2_category == filter_level2)

    # Pagination
    total = query.count()
    comments = query.order_by(Comment.created_at.desc())\
                    .offset((page - 1) * settings.PER_PAGE)\
                    .limit(settings.PER_PAGE)\
                    .all()

    # Get counts
    good_count = db.query(Comment).filter(Comment.level1_category == "good").count()
    bad_count = db.query(Comment).filter(Comment.level1_category == "bad").count()
    pending_count = db.query(Comment).filter(Comment.is_reviewed == False).count()
    logger.debug(" route called 3")
    # Get unique categories for filters
    categories = db.query(Comment.level2_category)\
                   .filter(Comment.level2_category.isnot(None))\
                   .distinct()\
                   .all()
    logger.debug(" route called 5")
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "comments": comments,
            "page": page,
            "total_pages": (total + settings.PER_PAGE - 1) // settings.PER_PAGE,
            "total": total,
            "good_count": good_count,
            "bad_count": bad_count,
            "pending_count": pending_count,
            "filter_level1": filter_level1,
            "filter_level2": filter_level2,
            "categories": [c[0] for c in categories if c[0]]
        }
    )
    logger.debug(" route called 6")
# Health check
@app.get("/health")
async def health_check():
    logger.debug(" route called 4")
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "timestamp": datetime.now().isoformat()
    }
    logger.debug(" route called 7")

from sqlalchemy import inspect
from app.models.database import engine

@app.get("/debug/db")
async def debug_db():
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    return {
        "database_url": str(engine.url),
        "tables": tables,
        "users_exists": "users" in tables
    }
@app.get("/debug/template")
async def debug_template():
    # start_up= startup_event()
    # start_up = await startup_event()
    return {

        "admin_verification_1": check_admin_1,
        "admin_verification_2": check_admin_4,
        "admin_verification_3": check_admin_3
    }




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=settings.DEBUG)