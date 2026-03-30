
from fastapi import APIRouter, Request, Depends, HTTPException, Query, Form
# from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import Optional, List
# import pandas as pd
import json
from datetime import datetime, timedelta
import hashlib
from fastapi import Body
# Change these imports
from app.models.database import get_db, Comment, TrainingData
from app.models.database import User  # Add this import
from app.services.classifier import classifier
from app.services.encryption import encrypt_content, decrypt_content
from app.utils.helpers import get_current_user, admin_required
from app.models.database import ExtractionJob 
# At the top of the file, add imports
from pydantic import BaseModel
from typing import List
from app.utils.helpers import notify_admins
import logging
from app.models.database import PredefinedFilter, CustomFilter
logger = logging.getLogger(__name__)

# Pydantic model for batch review
class BatchReviewRequest(BaseModel):
    comment_ids: List[str]
    action: str  # "approve", "reject", or "flag"

router = APIRouter()
# templates = Jinja2Templates(directory="app/templates")
from app.template import templates

@router.get("/", response_class=HTMLResponse)
async def list_comments(
    request: Request,
    page: int = 1,
    per_page: int = Query(20, le=100),
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter_level1: Optional[str] = None,
    filter_level2: Optional[str] = None,
    filter_author: Optional[str] = None,
    filter_video: Optional[str] = None,
    search: Optional[str] = None,
    reviewed_only: bool = False,
    unreviewed_only: bool = False,
    review_status: Optional[str] = None,
    job_id: Optional[str] = None,                     # new filter
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Build query
    query = db.query(Comment)

    # Apply filters
    if filter_level1:
        query = query.filter(Comment.level1_category == filter_level1)
    if filter_level2:
        query = query.filter(Comment.level2_category == filter_level2)
    if filter_author:
        query = query.filter(Comment.author.ilike(f"%{filter_author}%"))
    if filter_video:
        query = query.filter(Comment.video_title.ilike(f"%{filter_video}%"))
    if search:
        query = query.filter(Comment.content.ilike(f"%{search}%"))
    if review_status == 'reviewed':
        query = query.filter(Comment.is_reviewed == True)
    elif review_status == 'unreviewed':
        query = query.filter(Comment.is_reviewed == False)
    if job_id:
        query = query.filter(Comment.extraction_job_id == job_id)

    # Apply sorting
    if sort_order == "desc":
        query = query.order_by(getattr(Comment, sort_by).desc())
    else:
        query = query.order_by(getattr(Comment, sort_by).asc())

    # Get total count for pagination
    total = query.count()
    comments = query.offset((page - 1) * per_page).limit(per_page).all()

    # Decrypt content for display
    for comment in comments:
        try:
            comment.content = decrypt_content(comment.content)
        except:
            comment.content = "[Encrypted Content]"

    # --- Compute stats based on filter (global or per job) ---
    stats_query = db.query(Comment)
    if job_id:
        stats_query = stats_query.filter(Comment.extraction_job_id == job_id)

    stats = {
        "total": stats_query.count(),
        "good": stats_query.filter(Comment.level1_category == "good").count(),
        "bad": stats_query.filter(Comment.level1_category == "bad").count(),
        "unreviewed": stats_query.filter(Comment.is_reviewed == False).count()
    }

    # --- Get user's jobs with their own stats ---
    user_jobs = db.query(ExtractionJob).filter(ExtractionJob.user_id == user.id).order_by(ExtractionJob.requested_at.desc()).all()
    jobs_with_stats = []
    for job in user_jobs:
        # Counts for this job
        job_comments = db.query(Comment).filter(Comment.extraction_job_id == job.job_id)
        total = job_comments.count()
        good = job_comments.filter(Comment.level1_category == "good").count()
        bad = job_comments.filter(Comment.level1_category == "bad").count()
        neutral = job_comments.filter(Comment.is_reviewed == True, Comment.level1_category.is_(None)).count()
        pending = job_comments.filter(Comment.is_reviewed == False).count()
        jobs_with_stats.append({
            "job": job,
            "total": total,
            "good": good,
            "bad": bad,
            "neutral": neutral,
            "pending": pending,
            "progress": int((good + bad + neutral) / total * 100) if total else 0
        })

    return templates.TemplateResponse(
        "comments/list.html",
        {
            "request": request,
            "user": user,
            "comments": comments,
            "stats": stats,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "filters": {
                "level1": filter_level1,
                "level2": filter_level2,
                "author": filter_author,
                "video": filter_video,
                "search": search,
                "job_id": job_id,               # include current job_id for pagination links
            },
            "jobs_with_stats": jobs_with_stats,
            "selected_job_id": job_id,
        }
    )
@router.get("/{comment_id}")
async def get_comment(
    comment_id: str,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get single comment details"""
    comment = db.query(Comment).filter(Comment.comment_id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Decrypt content
    comment.content = decrypt_content(comment.content)

    return JSONResponse({
        "success": True,
        "comment": comment.to_dict()
    })

@router.post("/batch/review")
async def batch_review(
    request: Request,
    data: BatchReviewRequest,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    comment_ids = data.comment_ids
    action = data.action

    if not comment_ids:
        raise HTTPException(400, "No comment IDs provided")

    actions_map = {
        "good": {"level1": "good", "reviewed": True, "approved": True},
        "bad":  {"level1": "bad",  "reviewed": True, "approved": False},
        "neutral": {"level1": "neutral", "reviewed": True, "approved": False},
    }

    if action not in actions_map:
        raise HTTPException(400, f"Invalid action: {action}")

    comments = db.query(Comment).filter(Comment.comment_id.in_(comment_ids)).all()
    for c in comments:
        if actions_map[action]["level1"] is not None:
            c.level1_category = actions_map[action]["level1"]
        c.is_reviewed = True
        c.is_approved = actions_map[action]["approved"]
        c.reviewed_by = user.username
        c.reviewed_at = datetime.utcnow()

    db.commit()

    # If HTMX request, return the refreshed HTML (or redirect)
    if request.headers.get("HX-Request"):
        # Redirect to the current URL – HTMX will replace the container
        return RedirectResponse(url=request.headers.get("HX-Current-URL", "/comments"), status_code=200)
    else:
        return {"success": True, "message": f"{len(comments)} comments updated"}


# @router.post("/batch/review")
# async def batch_review(
#     request: Request,
#     data: BatchReviewRequest,
#     user = Depends(get_current_user),  # any authenticated user can use it
#     db: Session = Depends(get_db)
# ):
#     comment_ids = data.comment_ids
#     action = data.action

#     if not comment_ids:
#         raise HTTPException(400, "No comment IDs provided")

#     # Map action to database updates
#     actions = {
#         "good": {"level1": "good", "reviewed": True, "approved": True},
#         "bad":  {"level1": "bad",  "reviewed": True, "approved": False},
#         "neutral": {"level1": None, "reviewed": True, "approved": False},
#     }

#     if action not in actions:
#         raise HTTPException(400, f"Invalid action: {action}")

#     comments = db.query(Comment).filter(Comment.comment_id.in_(comment_ids)).all()
#     for c in comments:
#         if actions[action]["level1"] is not None:
#             c.level1_category = actions[action]["level1"]
#         c.is_reviewed = True
#         c.is_approved = actions[action]["approved"]
#         c.reviewed_by = user.username
#         c.reviewed_at = datetime.utcnow()

#     db.commit()
#     notify_admins(db, f"User {user.username} marked {len(comment_ids)} comments as '{action}'.")
#     return {"success": True, "message": f"{len(comments)} comments updated"}


# @router.post("/batch/review")
# async def batch_review(
#     data: BatchReviewRequest,
#     user = Depends(get_current_user),   # ✅ now any user can do this
#     db: Session = Depends(get_db)
# ):
#     """Batch mark comments as Good, Bad, or Neutral."""
#     comment_ids = data.comment_ids
#     action = data.action

#     if not comment_ids:
#         raise HTTPException(400, "No comment IDs provided")

#     # Define what each action does
#     actions_map = {
#         "good": {"level1": "good", "reviewed": True, "approved": True},
#         "bad":  {"level1": "bad",  "reviewed": True, "approved": False},
#         "neutral": {"level1": None, "reviewed": True, "approved": False},   # keep original level1, just mark reviewed
#     }

#     if action not in actions_map:
#         raise HTTPException(400, f"Invalid action: {action}")

#     comments = db.query(Comment).filter(Comment.comment_id.in_(comment_ids)).all()
#     for c in comments:
#         if actions_map[action]["level1"] is not None:
#             c.level1_category = actions_map[action]["level1"]
#         c.is_reviewed = True
#         c.is_approved = actions_map[action]["approved"]
#         c.reviewed_by = user.username
#         c.reviewed_at = datetime.utcnow()

#     db.commit()
#     return {"success": True, "message": f"{len(comments)} comments updated"}

# @router.post("/batch/level2")
# async def batch_set_level2(
#     data: dict = Body(...),
#     user = Depends(get_current_user),
#     db: Session = Depends(get_db)
# ):
#     comment_ids = data.get("comment_ids", [])
#     level2 = data.get("level2")
#     if not comment_ids or not level2:
#         raise HTTPException(400, "Missing comment_ids or level2")
#     comments = db.query(Comment).filter(Comment.comment_id.in_(comment_ids)).all()
#     for c in comments:
#         c.level2_category = level2
#     db.commit()
#     return {"success": True}

# @router.post("/batch/level3")
# async def batch_set_level3(
#     data: dict = Body(...),
#     user = Depends(get_current_user),
#     db: Session = Depends(get_db)
# ):
#     comment_ids = data.get("comment_ids", [])
#     level3 = data.get("level3")
#     if not comment_ids or not level3:
#         raise HTTPException(400, "Missing comment_ids or level3")
#     comments = db.query(Comment).filter(Comment.comment_id.in_(comment_ids)).all()
#     for c in comments:
#         c.level3_subcategory = level3
#     db.commit()
#     return {"success": True}

@router.post("/batch/level2")
async def batch_set_level2(data: dict = Body(...), user=Depends(get_current_user), db: Session = Depends(get_db)):
    comment_ids = data.get("comment_ids", [])
    level2 = data.get("level2")
    if not comment_ids or not level2:
        raise HTTPException(400, "Missing comment_ids or level2")
    comments = db.query(Comment).filter(Comment.comment_id.in_(comment_ids)).all()
    for c in comments:
        c.level2_category = level2
    db.commit()
    return {"success": True}

@router.post("/batch/level3")
async def batch_set_level3(data: dict = Body(...), user=Depends(get_current_user), db: Session = Depends(get_db)):
    comment_ids = data.get("comment_ids", [])
    level3 = data.get("level3")
    if not comment_ids or not level3:
        raise HTTPException(400, "Missing comment_ids or level3")
    comments = db.query(Comment).filter(Comment.comment_id.in_(comment_ids)).all()
    for c in comments:
        c.level3_subcategory = level3
    db.commit()
    return {"success": True}
@router.get("/level2/{category_id}/subcategories")
async def get_subcategories(category_id: int, db: Session = Depends(get_db)):
    subcats = db.query(Level3Subcategory).filter(
        Level3Subcategory.category_id == category_id,
        Level3Subcategory.is_active == True
    ).order_by(Level3Subcategory.order).all()
    return [{"id": sc.id, "name": sc.name} for sc in subcats]

@router.delete("/{comment_id}")
async def delete_comment(
    comment_id: str,
    user = Depends(admin_required),
    db: Session = Depends(get_db)
):
    """Delete a comment"""

    comment = db.query(Comment).filter(Comment.comment_id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    db.delete(comment)
    db.commit()

    return JSONResponse({
        "success": True,
        "message": "Comment deleted successfully"
    })

@router.post("/{comment_id}/reclassify")
async def reclassify_comment(
    comment_id: str,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Re-run classification on a comment"""

    comment = db.query(Comment).filter(Comment.comment_id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Decrypt content
    content = decrypt_content(comment.content)

    # Run classification
    result = classifier.classify_comment(content)

    # Update comment
    comment.level1_category = result["level1"]["category"]
    comment.level1_confidence = result["level1"]["confidence"]
    comment.level1_scores = result["level1"]["scores"]

    comment.level2_category = result["level2"]["category"]
    comment.level2_confidence = result["level2"]["confidence"]
    comment.level2_scores = result["level2"]["scores"]

    comment.level3_subcategory = result["level3"]["category"]
    comment.level3_confidence = result["level3"]["confidence"]
    comment.level3_scores = result["level3"]["scores"]

    comment.processed_at = datetime.utcnow()
    db.commit()

    return JSONResponse({
        "success": True,
        "result": result
    })

@router.get("/export/download")
async def export_comments(
    format: str = "csv",
    filter_level1: Optional[str] = None,
    filter_level2: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user = Depends(admin_required),
    db: Session = Depends(get_db)
):
    """Export comments to file"""

    # Build query
    query = db.query(Comment)

    if filter_level1:
        query = query.filter(Comment.level1_category == filter_level1)
    if filter_level2:
        query = query.filter(Comment.level2_category == filter_level2)
    if start_date:
        query = query.filter(Comment.created_at >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(Comment.created_at <= datetime.fromisoformat(end_date))

    comments = query.all()

    # Prepare data
    data = []
    for c in comments:
        try:
            content = decrypt_content(c.content)
        except:
            content = "[Encrypted]"

        data.append({
            "comment_id": c.comment_id,
            "content": content,
            "author": c.author,
            "video_title": c.video_title,
            "video_id": c.video_id,
            "published_at": c.published_at.isoformat() if c.published_at else "",
            "like_count": c.like_count,
            "level1_category": c.level1_category,
            "level1_confidence": c.level1_confidence,
            "level2_category": c.level2_category or "",
            "level2_confidence": c.level2_confidence or 0,
            "level3_subcategory": c.level3_subcategory or "",
            "level3_confidence": c.level3_confidence or 0,
            "is_reviewed": c.is_reviewed,
            "reviewed_by": c.reviewed_by or "",
            "reviewed_at": c.reviewed_at.isoformat() if c.reviewed_at else "",
            "is_approved": c.is_approved,
            "is_flagged": c.is_flagged,
            "source": c.source or "",
            "created_at": c.created_at.isoformat() if c.created_at else ""
        })

    # Create DataFrame
    df = pd.DataFrame(data)

    # Save to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"exports/comments_export_{timestamp}.{format}"

    import os
    os.makedirs("exports", exist_ok=True)

    import csv, json
    if format == "csv":
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            if data:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
        media_type = "text/csv"
    elif format == "json":
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        media_type = "application/json"
    elif format == "excel":
        # Optional: implement with openpyxl (already installed)
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        if data:
            ws.append(list(data[0].keys()))
            for row in data:
                ws.append(list(row.values()))
        wb.save(filename)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        raise HTTPException(status_code=400, detail="Unsupported format")

    return FileResponse(
        filename,
        media_type=media_type,
        filename=f"comments_export_{timestamp}.{format}"
    )

@router.get("/stats/summary")
async def get_comments_stats(
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive comment statistics"""

    total = db.query(Comment).count()
    good = db.query(Comment).filter(Comment.level1_category == "good").count()
    bad = db.query(Comment).filter(Comment.level1_category == "bad").count()
    unreviewed = db.query(Comment).filter(Comment.is_reviewed == False).count()
    flagged = db.query(Comment).filter(Comment.is_flagged == True).count()

    # Category breakdown
    categories = {}
    for cat in ["Harassment & Bullying", "Hate Speech", "Adult & Sexual Content",
                "Violence & Gore", "Spam & Manipulation", "Misinformation"]:
        count = db.query(Comment).filter(Comment.level2_category == cat).count()
        if count > 0:
            categories[cat] = count

    # Daily trends (last 7 days)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    daily_counts = db.query(
        db.func.date(Comment.created_at).label('date'),
        db.func.count().label('count')
    ).filter(Comment.created_at >= seven_days_ago)\
     .group_by('date')\
     .all()

    trends = {str(row.date): row.count for row in daily_counts}

    return JSONResponse({
        "success": True,
        "stats": {
            "total": total,
            "good": good,
            "bad": bad,
            "unreviewed": unreviewed,
            "flagged": flagged,
            "review_completion": (total - unreviewed) / total * 100 if total > 0 else 0,
            "bad_percentage": bad / total * 100 if total > 0 else 0,
            "categories": categories,
            "daily_trends": trends
        }
    })

from app.models.database import CustomFilter

@router.get("/filters/my", response_class=HTMLResponse)
async def my_custom_filters(request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    filters = db.query(CustomFilter).filter(CustomFilter.user_id == user.id).all()
    return templates.TemplateResponse("filters/my_custom_filters.html", {"request": request, "user": user, "filters": filters})

@router.post("/filters/custom/add")
async def add_custom_filter(
    phrase: str = Form(...),
    category: str = Form(None),
    action: str = Form("mark_bad"),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    filter = CustomFilter(user_id=user.id, phrase=phrase, category=category, action=action)
    db.add(filter)
    db.commit()
    return JSONResponse({"success": True})

@router.post("/filters/custom/{filter_id}/delete")
async def delete_custom_filter(filter_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    filter = db.query(CustomFilter).filter(CustomFilter.id == filter_id, CustomFilter.user_id == user.id).first()
    if filter:
        db.delete(filter)
        db.commit()
    return JSONResponse({"success": True})

@router.post("/apply-filters")
async def apply_filters(
    data: dict = Body(...),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    comment_ids = data.get("comment_ids", [])
    filter_type = data.get("filter_type")  # "predefined" or "custom"
    if not comment_ids:
        raise HTTPException(400, "No comment IDs provided")
    if filter_type not in ["predefined", "custom"]:
        raise HTTPException(400, "Invalid filter type")

    comments = db.query(Comment).filter(Comment.comment_id.in_(comment_ids)).all()
    if not comments:
        return {"success": True, "message": "No comments to process"}

    # Get filters
    if filter_type == "predefined":
        filters = db.query(PredefinedFilter).filter(PredefinedFilter.is_active == True).all()
    else:
        filters = db.query(CustomFilter).filter(CustomFilter.user_id == user.id).all()

    phrases = [f.phrase.lower() for f in filters]
    updated = 0
    for c in comments:
        # Decrypt content
        content = decrypt_content(c.content).lower()
        if any(phrase in content for phrase in phrases):
            # Default action: mark as bad and reviewed
            c.level1_category = "bad"
            c.is_reviewed = True
            c.is_approved = False
            updated += 1

    db.commit()
    return {"success": True, "message": f"Updated {updated} comments"}