# app/routers/admin.py - Update imports

from fastapi import APIRouter, Request, Depends, HTTPException, Form, UploadFile, File, BackgroundTasks
# from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from sqlalchemy.orm import Session
from typing import Optional
# import pandas as pd
import json
import os
from datetime import datetime, timedelta

# Change these imports
# from app.models.database import get_db, get_db, Comment, TrainingData, ExtractionJob, ExtractionPattern
from app.models.database import get_db, Comment, TrainingData
# from app.models.extraction import   ExtractionJob, ExtractionPattern
from app.models.database import ExtractionJob
from app.models.extraction import ExtractionPattern

# from app.models.user import User  # Add this import
from app.models.database import User
from app.config import settings
from app.utils.helpers import get_current_user, get_password_hash, admin_required, pattern_to_regex
from app.services.classifier import classifier, LEVEL2_CATEGORIES, LEVEL3_SUBCATEGORIES
from app.services.youtube_extractor import youtube_extractor

router = APIRouter()
# templates = Jinja2Templates(directory="app/templates")
from app.template import templates
# ... rest of the file remains the same

@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    user = Depends(admin_required)
):
    mysql_db = next(get_db())
    sqlite_db = next(get_db())

    # Get statistics
    total_users = mysql_db.query(User).count()
    total_comments = sqlite_db.query(Comment).count()
    bad_comments = sqlite_db.query(Comment).filter(Comment.level1_category == "bad").count()
    unverified = sqlite_db.query(Comment).filter(Comment.is_reviewed == False).count()

    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "user": user,
            "total_users": total_users,
            "total_comments": total_comments,
            "bad_comments": bad_comments,
            "unverified": unverified
        }
    )

@router.get("/users", response_class=HTMLResponse)
async def admin_users(
    request: Request,
    page: int = 1,
    user = Depends(admin_required),
    db: Session = Depends(get_db)
):
    users = db.query(User).offset((page - 1) * settings.PER_PAGE).limit(settings.PER_PAGE).all()
    total = db.query(User).count()

    return templates.TemplateResponse(
        "admin/users.html",
        {
            "request": request,
            "user": user,
            "users": users,
            "page": page,
            "total_pages": (total + settings.PER_PAGE - 1) // settings.PER_PAGE,
            "total": total
        }
    )

@router.post("/users/add")
async def admin_add_user(
    request: Request,
    username: str = Form(...),
    name: str = Form(...),
    password: str = Form(...),
    is_admin: bool = Form(False),
    user = Depends(admin_required),
    db: Session = Depends(get_db)
):
    # Check if username exists
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        return templates.TemplateResponse(
            "admin/add_user.html",
            {
                "request": request,
                "user": user,
                "error": "Username already exists"
            }
        )

    # Create user
    new_user = User(
        username=username,
        name=name,
        password=get_password_hash(password),
        is_admin=is_admin
    )

    db.add(new_user)
    db.commit()

    return RedirectResponse(url="/admin/users", status_code=302)

@router.get("/users/{user_id}/toggle-admin")
async def toggle_admin(
    user_id: int,
    user = Depends(admin_required),
    db: Session = Depends(get_db)
):
    target_user = db.query(User).filter(User.id == user_id).first()
    if target_user and target_user.username != "admin":  # Can't demote main admin
        target_user.is_admin = not target_user.is_admin
        db.commit()

    return RedirectResponse(url="/admin/users", status_code=302)

@router.get("/users/{user_id}/delete")
async def delete_user(
    user_id: int,
    user = Depends(admin_required),
    db: Session = Depends(get_db)
):
    target_user = db.query(User).filter(User.id == user_id).first()
    if target_user and target_user.username != "admin":  # Can't delete main admin
        db.delete(target_user)
        db.commit()

    return RedirectResponse(url="/admin/users", status_code=302)

@router.get("/comments", response_class=HTMLResponse)
async def admin_comments(
    request: Request,
    page: int = 1,
    filter_level1: Optional[str] = None,
    filter_level2: Optional[str] = None,
    user = Depends(admin_required),
    db: Session = Depends(get_db)
):
    query = db.query(Comment)
    if filter_level1:
        query = query.filter(Comment.level1_category == filter_level1)
    if filter_level2:
        query = query.filter(Comment.level2_category == filter_level2)

    total = query.count()
    comments = query.order_by(Comment.created_at.desc())\
                    .offset((page - 1) * settings.PER_PAGE)\
                    .limit(settings.PER_PAGE)\
                    .all()

    return templates.TemplateResponse(
        "admin/comments.html",
        {
            "request": request,
            "user": user,
            "comments": comments,
            "page": page,
            "total_pages": (total + settings.PER_PAGE - 1) // settings.PER_PAGE,
            "filter_level1": filter_level1,
            "filter_level2": filter_level2,
            "categories": LEVEL2_CATEGORIES.keys()
        }
    )

@router.post("/comments/{comment_id}/review")
async def review_comment(
    comment_id: str,
    request: Request,
    level1: str = Form(...),
    level2: str = Form(...),
    level3: str = Form(...),
    user = Depends(admin_required),
    db: Session = Depends(get_db)
):
    comment = db.query(Comment).filter(Comment.comment_id == comment_id).first()
    if comment:
        # Update classification
        comment.level1_category = level1
        comment.level2_category = level2
        comment.level3_subcategory = level3
        comment.is_reviewed = True
        comment.reviewed_by = user.username
        comment.reviewed_at = datetime.utcnow()
        comment.is_approved = True

        # Add to training data
        training = TrainingData(
            comment_id=comment.comment_id,
            content=comment.content,
            level1_category=level1,
            level2_category=level2,
            level3_subcategory=level3,
            is_verified=True,
            verified_by=user.username
        )
        db.add(training)
        db.commit()

        # Retrain model if enough new data
        training_count = db.query(TrainingData).count()
        if training_count % 50 == 0:  # Retrain every 50 new samples
            training_data = db.query(TrainingData).all()
            training_list = [
                {
                    "content": t.content,
                    "level1_category": t.level1_category,
                    "level2_category": t.level2_category,
                    "level3_subcategory": t.level3_subcategory
                }
                for t in training_data
            ]
            classifier.retrain_with_feedback(training_list)

    return RedirectResponse(url="/admin/comments", status_code=302)

@router.get("/youtube-extract", response_class=HTMLResponse)
async def youtube_extract_page(
    request: Request,
    user = Depends(admin_required)
):
    return templates.TemplateResponse(
        "admin/youtube_extract.html",
        {
            "request": request,
            "user": user
        }
    )

@router.post("/youtube-extract")
async def youtube_extract(
    request: Request,
    url: str = Form(...),
    max_comments: int = Form(500),
    user = Depends(admin_required)
):
    try:
        # Process YouTube URL
        result = await youtube_extractor.process_youtube_url(url, max_comments)

        # Save comments to database
        sqlite_db = next(get_db())
        for comment_data in result["comments"]:
            comment = Comment(
                comment_id=comment_data["comment_id"],
                content=comment_data["content"],
                author=comment_data["author"],
                video_id=comment_data["video_id"],
                video_title=comment_data["video_title"],
                published_at=datetime.fromtimestamp(comment_data["published_at"]) if comment_data["published_at"] else None,
                like_count=comment_data["like_count"],
                level1_category=comment_data.get("level1", {}).get("category"),
                level2_category=comment_data.get("level2", {}).get("category"),
                level3_subcategory=comment_data.get("level3", {}).get("category"),
                confidence_scores=comment_data.get("level1", {}).get("scores", {}),
                source_file=result["csv_file"],
                source_level=1
            )
            sqlite_db.add(comment)

        sqlite_db.commit()

        return JSONResponse({
            "success": True,
            "message": f"Extracted {result['total_extracted']} comments",
            "stats": result["stats"],
            "video_info": result["video_info"]
        })

    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        })

@router.get("/export/comments")
async def export_comments(
    format: str = "csv",
    filter_level1: Optional[str] = None,
    filter_level2: Optional[str] = None,
    user = Depends(admin_required),
    db: Session = Depends(get_db)
):
    # Build query
    query = db.query(Comment)
    if filter_level1:
        query = query.filter(Comment.level1_category == filter_level1)
    if filter_level2:
        query = query.filter(Comment.level2_category == filter_level2)

    comments = query.all()

    # Prepare data
    data = []
    for c in comments:
        data.append({
            "comment_id": c.comment_id,
            "content": c.content,
            "author": c.author,
            "video_title": c.video_title,
            "level1": c.level1_category,
            "level2": c.level2_category,
            "level3": c.level3_subcategory,
            "is_bad": 1 if c.level1_category == "bad" else 0,
            "is_reviewed": c.is_reviewed,
            "reviewed_by": c.reviewed_by,
            "created_at": c.created_at
        })

    # Create DataFrame
    df = pd.DataFrame(data)

    # Save to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"exports/comments_export_{timestamp}.{format}"
    os.makedirs("exports", exist_ok=True)

    if format == "csv":
        df.to_csv(filename, index=False, encoding='utf-8-sig')
    elif format == "json":
        df.to_json(filename, orient="records", indent=2)
    elif format == "excel":
        df.to_excel(filename, index=False)

    return FileResponse(
        filename,
        media_type="application/octet-stream",
        filename=f"comments_export.{format}"
    )

@router.get("/retrain-model")
async def retrain_model(
    user = Depends(admin_required),
    db: Session = Depends(get_db)
):
    try:
        # Get verified training data
        training_data = db.query(TrainingData).filter(TrainingData.is_verified == True).all()

        if len(training_data) < 10:
            return JSONResponse({
                "success": False,
                "error": "Need at least 10 verified samples to retrain"
            })

        # Prepare data
        training_list = [
            {
                "content": t.content,
                "level1_category": t.level1_category,
                "level2_category": t.level2_category,
                "level3_subcategory": t.level3_subcategory
            }
            for t in training_data
        ]

        # Retrain models
        success = classifier.retrain_with_feedback(training_list)

        return JSONResponse({
            "success": success,
            "message": f"Models retrained with {len(training_data)} samples",
            "samples_used": len(training_data)
        })

    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        })

# Pattern Management Routes
@router.get("/patterns", response_class=HTMLResponse)
async def admin_patterns(
    request: Request,
    user = Depends(admin_required),
    db: Session = Depends(get_db)
):
    patterns = db.query(ExtractionPattern).all()
    return templates.TemplateResponse(
        "admin/patterns.html",
        {
            "request": request,
            "user": user,
            "patterns": patterns
        }
    )

@router.post("/patterns/add")
async def add_pattern(
    request: Request,
    name: str = Form(...),
    pattern_format: str = Form(...),
    description: str = Form(...),
    user = Depends(admin_required),
    db: Session = Depends(get_db)
):
    # Generate regex from pattern
    from app.utils.helpers import pattern_to_regex
    regex_pattern = pattern_to_regex(pattern_format)

    pattern = ExtractionPattern(
        name=name,
        pattern_format=pattern_format,
        regex_pattern=regex_pattern,
        description=description,
        created_by=user.username
    )

    db.add(pattern)
    db.commit()

    return RedirectResponse(url="/admin/patterns", status_code=302)

@router.get("/patterns/{pattern_id}/set-active")
async def set_active_pattern(
    pattern_id: int,
    user = Depends(admin_required),
    db: Session = Depends(get_db)
):
    # Deactivate all patterns
    db.query(ExtractionPattern).update({"is_active": False})

    # Activate selected pattern
    pattern = db.query(ExtractionPattern).filter(ExtractionPattern.id == pattern_id).first()
    if pattern:
        pattern.is_active = True
        db.commit()

    return RedirectResponse(url="/admin/patterns", status_code=302)

@router.get("/patterns/{pattern_id}/delete")
async def delete_pattern(
    pattern_id: int,
    user = Depends(admin_required),
    db: Session = Depends(get_db)
):
    pattern = db.query(ExtractionPattern).filter(ExtractionPattern.id == pattern_id).first()
    if pattern:
        db.delete(pattern)
        db.commit()

    return RedirectResponse(url="/admin/patterns", status_code=302)


# app/routers/admin.py

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.models.database import get_db, ExtractionJob, User, Comment
from app.utils.helpers import admin_required
from app.services.classifier import classifier
import csv
import io

router = APIRouter()

@router.get("/extraction-jobs", response_class=HTMLResponse)
async def admin_extraction_jobs_page(
    request: Request,
    admin_user: User = Depends(admin_required),
    db: Session = Depends(get_db)
):
    """Admin page to view extraction jobs and upload CSV files."""
    jobs = db.query(ExtractionJob).order_by(ExtractionJob.requested_at.desc()).all()
    return templates.TemplateResponse(
        "admin/extraction_jobs.html",
        {"request": request, "user": admin_user, "jobs": jobs}
    )

@router.get("/api/extraction-jobs")
async def list_extraction_jobs_api(
    db: Session = Depends(get_db),
    admin_user: User = Depends(admin_required)
):
    jobs = db.query(ExtractionJob).order_by(ExtractionJob.requested_at.desc()).all()
    return [{
        "job_id": j.job_id,
        "user_id": j.user_id,
        "username": j.user.username,
        "video_url": j.video_url,
        "video_title": j.video_title,
        "status": j.status,
        "requested_at": j.requested_at,
        "comment_count": j.comment_count
    } for j in jobs]

@router.post("/extraction-jobs/{job_id}/upload-csv")
async def upload_csv_for_job(
    job_id: str,
    csv_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin_user: User = Depends(admin_required)
):
    # 1. Get the job
    job = db.query(ExtractionJob).filter(ExtractionJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "pending":
        raise HTTPException(status_code=400, detail="Job already processed")

    # 2. Read CSV content
    content = await csv_file.read()
    try:
        decoded = content.decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV: {e}")

    # 3. Process each row (we'll assume the CSV contains the necessary columns)
    #    The expected columns: comment_id, video_id, video_title, author, author_id, content, published_at, like_count, reply_count, is_reply, parent_id
    #    Additional columns for classification (if present) will be used; otherwise we classify here.
    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=400, detail="CSV is empty")

    # Update job status to processing
    job.status = "processing"
    job.started_at = datetime.utcnow()
    db.commit()

    good_count = 0
    bad_count = 0
    inserted_count = 0

    for row in rows:
        try:
            # Prepare comment data
            comment_data = {
                "comment_id": row.get("comment_id"),
                "video_id": job.video_id,  # use job's video_id
                "video_title": row.get("video_title", job.video_title or ""),
                "author": row.get("author"),
                "author_id": row.get("author_id"),
                "content": row.get("content"),
                "published_at": datetime.fromisoformat(row["published_at"]) if row.get("published_at") else None,
                "like_count": int(row.get("like_count", 0)),
                "reply_count": int(row.get("reply_count", 0)),
                "is_reply": row.get("is_reply", "False").lower() in ("true", "1", "yes"),
                "parent_id": row.get("parent_id"),
                "extraction_job_id": job.job_id
            }

            # If classification columns exist in CSV, use them; else classify
            if "level1_category" in row and row["level1_category"]:
                # Use pre-classified
                comment_data.update({
                    "level1_category": row.get("level1_category"),
                    "level1_confidence": float(row.get("level1_confidence", 1.0)),
                    "level2_category": row.get("level2_category"),
                    "level2_confidence": float(row.get("level2_confidence", 1.0)),
                    "level3_subcategory": row.get("level3_subcategory"),
                    "level3_confidence": float(row.get("level3_confidence", 1.0)),
                })
            else:
                # Run classification
                classification = classifier.classify_comment(comment_data["content"])
                comment_data.update(classification)

            # Save to database
            comment = Comment(**comment_data)
            db.add(comment)
            inserted_count += 1

            # Count good/bad
            if comment.level1_category == "good":
                good_count += 1
            elif comment.level1_category == "bad":
                bad_count += 1

            # Flush every 100 rows to avoid memory issues
            if inserted_count % 100 == 0:
                db.flush()

        except Exception as e:
            # Log error and continue (or stop? Let's log and continue)
            print(f"Error processing row: {e}")

    # Update job status
    job.status = "completed"
    job.completed_at = datetime.utcnow()
    job.comment_count = inserted_count
    job.good_count = good_count
    job.bad_count = bad_count
    # Store the uploaded CSV path if desired (we can save the file to disk)
    # For now, we don't store the file permanently.
    from app.models.database import Notification  # ensure this import is at the top

# ... inside upload_csv_for_job, after job.status = "completed" and after updating counts
    notification = Notification(
        user_id=job.user_id,
        message=f"Your extraction job for {job.video_title or job.video_url} is ready! View your comments.",
        is_read=False
    )
    db.add(notification)
    db.commit()

    return {"message": f"Successfully processed {inserted_count} comments", "good": good_count, "bad": bad_count}


@router.get("/stats")
async def admin_stats(
    db: Session = Depends(get_db),
    admin_user: User = Depends(admin_required)
):
    # 1. Total comments per user
    user_stats = db.query(
        User.username,
        func.count(Comment.id).label("total_comments")
    ).join(ExtractionJob, ExtractionJob.user_id == User.id)\
     .join(Comment, Comment.extraction_job_id == ExtractionJob.job_id)\
     .group_by(User.id).all()

    # 2. Comments per day
    day_stats = db.query(
        func.date(Comment.created_at).label("day"),
        func.count(Comment.id).label("count")
    ).group_by("day").order_by("day").all()

    # 3. Pending jobs count
    pending_count = db.query(ExtractionJob).filter(ExtractionJob.status == "pending").count()

    return {
        "user_stats": [{"username": u[0], "total": u[1]} for u in user_stats],
        "daily_stats": [{"date": d[0], "count": d[1]} for d in day_stats],
        "pending_jobs": pending_count
    }

from app.models.database import Notification

@router.post("/notify/{user_id}")
async def send_notification(
    user_id: int,
    message: str = Form(...),
    db: Session = Depends(get_db),
    admin_user: User = Depends(admin_required)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    notification = Notification(user_id=user_id, message=message)
    db.add(notification)
    db.commit()
    return {"message": "Notification sent"}

