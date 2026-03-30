from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.models.database import get_db, Comment
from app.utils.helpers import get_current_user
from app.services.encryption import decrypt_content
from app.template import templates

router = APIRouter()

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    page: int = 1,
    per_page: int = 20,
    filter_level1: str = Query(None),
    filter_level2: str = Query(None),
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Build query
    query = db.query(Comment)
    if filter_level1:
        query = query.filter(Comment.level1_category == filter_level1)
    if filter_level2:
        query = query.filter(Comment.level2_category == filter_level2)

    total = query.count()
    comments = query.order_by(Comment.created_at.desc()).offset((page-1)*per_page).limit(per_page).all()

    # Decrypt content
    for c in comments:
        try:
            c.content = decrypt_content(c.content)
        except:
            c.content = "[Decryption Failed]"

    # Statistics (adjust as needed)
    good_count = db.query(Comment).filter(Comment.level1_category == "good").count()
    bad_count = db.query(Comment).filter(Comment.level1_category == "bad").count()
    pending_count = db.query(Comment).filter(Comment.is_reviewed == False).count()

    # Get distinct level2 categories for filter
    categories = db.query(Comment.level2_category).distinct().all()
    categories = [cat[0] for cat in categories if cat[0]]

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "comments": comments,
            "total": total,
            "good_count": good_count,
            "bad_count": bad_count,
            "pending_count": pending_count,
            "page": page,
            "total_pages": (total + per_page - 1) // per_page,
            "filter_level1": filter_level1,
            "filter_level2": filter_level2,
            "categories": categories
        }
    )
    