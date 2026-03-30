# app/routers/admin.py

from fastapi import APIRouter, Request, Depends, HTTPException, Form, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
import json
import os
from datetime import datetime, timedelta
import csv
import io

# Imports for models
from app.models.database import get_db, Comment, TrainingData, ExtractionJob, User, Notification
from app.models.extraction import ExtractionPattern
from app.config import settings
from app.utils.helpers import get_current_user, get_password_hash, admin_required, pattern_to_regex
from app.services.classifier import classifier, LEVEL2_CATEGORIES, LEVEL3_SUBCATEGORIES
from app.services.youtube_extractor import youtube_extractor
from app.template import templates
from app.models.database import PredefinedFilter

from app.services.encryption import encrypt_content

from app.models.database import Level2Category, Level3Subcategory

def parse_datetime(date_str):
    if not date_str:
        return None
    # Try common formats
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None
router = APIRouter()



# ---------- Admin Dashboard ----------
@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    user = Depends(admin_required)
):
    db = next(get_db())
    total_users = db.query(User).count()
    total_comments = db.query(Comment).count()
    bad_comments = db.query(Comment).filter(Comment.level1_category == "bad").count()
    unverified = db.query(Comment).filter(Comment.is_reviewed == False).count()

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


# ---------- User Management ----------
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
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        return templates.TemplateResponse(
            "admin/add_user.html",
            {"request": request, "user": user, "error": "Username already exists"}
        )
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
    if target_user and target_user.username != "admin":
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
    if target_user and target_user.username != "admin":
        db.delete(target_user)
        db.commit()
    return RedirectResponse(url="/admin/users", status_code=302)


# ---------- Comment Management ----------
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
        comment.level1_category = level1
        comment.level2_category = level2
        comment.level3_subcategory = level3
        comment.is_reviewed = True
        comment.reviewed_by = user.username
        comment.reviewed_at = datetime.utcnow()
        comment.is_approved = True

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

        training_count = db.query(TrainingData).count()
        if training_count % 50 == 0:
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


# ---------- YouTube Extraction (Admin only) ----------
@router.get("/youtube-extract", response_class=HTMLResponse)
async def youtube_extract_page(
    request: Request,
    user = Depends(admin_required)
):
    return templates.TemplateResponse(
        "admin/youtube_extract.html",
        {"request": request, "user": user}
    )


@router.post("/youtube-extract")
async def youtube_extract(
    request: Request,
    url: str = Form(...),
    max_comments: int = Form(500),
    user = Depends(admin_required)
):
    try:
        result = await youtube_extractor.process_youtube_url(url, max_comments)
        sqlite_db = next(get_db())
        for comment_data in result["comments"]:
            comment = Comment(
                comment_id=comment_data["comment_id"],
                content=comment_data["content"],
                author=comment_data["author"],
                video_id=comment_data["video_id"],
                video_title=comment_data["video_title"],
                published_at=datetime.fromtimestamp(comment_data["published_at"]) if comment_data.get("published_at") else None,
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
        return JSONResponse({"success": False, "error": str(e)})


# ---------- Export Comments ----------
@router.get("/export/comments")
async def export_comments(
    format: str = "csv",
    filter_level1: Optional[str] = None,
    filter_level2: Optional[str] = None,
    user = Depends(admin_required),
    db: Session = Depends(get_db)
):
    # (code unchanged)
    pass


# ---------- Retrain Model ----------
@router.get("/retrain-model")
async def retrain_model(
    user = Depends(admin_required),
    db: Session = Depends(get_db)
):
    # (code unchanged)
    pass


# ---------- Pattern Management ----------
@router.get("/patterns", response_class=HTMLResponse)
async def admin_patterns(
    request: Request,
    user = Depends(admin_required),
    db: Session = Depends(get_db)
):
    patterns = db.query(ExtractionPattern).all()
    return templates.TemplateResponse(
        "admin/patterns.html",
        {"request": request, "user": user, "patterns": patterns}
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
    db.query(ExtractionPattern).update({"is_active": False})
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


# ---------- Extraction Jobs Management (Admin) ----------
@router.get("/extraction-jobs", response_class=HTMLResponse)
async def admin_extraction_jobs_page(
    request: Request,
    admin_user: User = Depends(admin_required),
    db: Session = Depends(get_db)
):
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
    job = db.query(ExtractionJob).filter(ExtractionJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "pending":
        raise HTTPException(status_code=400, detail="Job already processed")

    # Read CSV content, handling BOM
    content = await csv_file.read()
    try:
        # Remove BOM if present
        if content.startswith(b'\xef\xbb\xbf'):
            content = content[3:]
        decoded = content.decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV: {e}")

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
            # Prepare comment data with fallbacks
            comment_data = {
                "comment_id": row.get("comment_id"),
                "video_id": job.video_id,  # use job's video_id
                "video_title": job.video_title or "",  # fallback to job title
                "author": row.get("author"),
                "author_id": row.get("author_id"),  # may be None
                "content": row.get("content"),
                # Parse published_at robustly
                "published_at": parse_datetime(row.get("published_at")),
                "like_count": int(row.get("like_count", 0)),
                "reply_count": int(row.get("reply_count", 0)),
                "is_reply": row.get("is_reply", "False").lower() in ("true", "1", "yes"),
                "parent_id": row.get("parent_id"),
                "extraction_job_id": job.job_id
            }

            if comment_data["content"]:
                try:
                    comment_data["content"] = encrypt_content(comment_data["content"])
                except Exception as e:
                    print(f"Encryption failed for comment {comment_data.get('comment_id')}: {e}")
                    continue  # skip this comment

            # Handle classification columns (if present)
            if "level1" in row and row["level1"]:
                comment_data.update({
                    "level1_category": row.get("level1"),
                    "level1_confidence": float(row.get("level1_conf", 1.0)),
                    "level2_category": row.get("level2"),
                    "level2_confidence": float(row.get("level2_conf", 1.0)),
                    "level3_subcategory": row.get("level3"),
                    "level3_confidence": float(row.get("level3_conf", 1.0)),
                })
            else:
                # Run classification
                classification = classifier.classify_comment(comment_data["content"])
                comment_data.update(classification)

            # Save to database
            comment = Comment(**comment_data)
            db.add(comment)
            inserted_count += 1

            if comment.level1_category == "good":
                good_count += 1
            elif comment.level1_category == "bad":
                bad_count += 1

            if inserted_count % 100 == 0:
                db.flush()

        except Exception as e:
            print(f"Error processing row: {e}")

    # Update job status
    job.status = "completed"
    job.completed_at = datetime.utcnow()
    job.comment_count = inserted_count
    job.good_count = good_count
    job.bad_count = bad_count

    # Send notification to user
    notification = Notification(
        user_id=job.user_id,
        message=f"Your extraction job for {job.video_title or job.video_url} is ready! View your comments.",
        is_read=False
    )
    db.add(notification)

    db.commit()

    return {"message": f"Successfully processed {inserted_count} comments", "good": good_count, "bad": bad_count}

from app.models.database import PredefinedFilter

@router.get("/filters", response_class=HTMLResponse)
async def admin_filters(request: Request, user=Depends(admin_required), db: Session = Depends(get_db)):
    filters = db.query(PredefinedFilter).order_by(PredefinedFilter.created_at.desc()).all()
    return templates.TemplateResponse("admin/filters.html", {"request": request, "user": user, "filters": filters})

@router.post("/filters/add")
async def add_predefined_filter(
    phrase: str = Form(...),
    category: str = Form(None),
    action: str = Form("mark_bad"),
    is_active: bool = Form(True),
    user=Depends(admin_required),
    db: Session = Depends(get_db)
):
    filter = PredefinedFilter(
        phrase=phrase, category=category, action=action, is_active=is_active, created_by=user.id
    )
    db.add(filter)
    db.commit()
    return RedirectResponse(url="/admin/filters", status_code=302)

@router.post("/filters/{filter_id}/toggle")
async def toggle_filter(filter_id: int, user=Depends(admin_required), db: Session = Depends(get_db)):
    filter = db.query(PredefinedFilter).get(filter_id)
    if filter:
        filter.is_active = not filter.is_active
        db.commit()
    return RedirectResponse(url="/admin/filters", status_code=302)

@router.post("/filters/{filter_id}/delete")
async def delete_filter(filter_id: int, user=Depends(admin_required), db: Session = Depends(get_db)):
    filter = db.query(PredefinedFilter).get(filter_id)
    if filter:
        db.delete(filter)
        db.commit()
    return RedirectResponse(url="/admin/filters", status_code=302)

# @router.post("/filters/import-from-txt")
# async def import_filters(file: UploadFile = File(...), user=Depends(admin_required), db: Session = Depends(get_db)):
#     content = await file.read()
#     lines = content.decode('utf-8').splitlines()
#     for line in lines:
#         if not line.strip():
#             continue
#         parts = line.split(',')
#         if len(parts) >= 3:
#             category = parts[0].strip()
#             english_phrase = parts[1].strip()
#             existing = db.query(PredefinedFilter).filter(PredefinedFilter.phrase == english_phrase).first()
#             if not existing:
#                 filter = PredefinedFilter(
#                     phrase=english_phrase,
#                     category=category,
#                     action="mark_bad",
#                     is_active=True,
#                     created_by=user.id
#                 )
#                 db.add(filter)
#     db.commit()
#     return RedirectResponse(url="/admin/filters", status_code=302)

# v2 import-txt
import re



@router.post("/filters/import-from-txt")
async def import_filters_from_txt(
    file: UploadFile = File(...),
    language: str = Form("auto"),          # new field
    user = Depends(admin_required),
    db: Session = Depends(get_db)
):
    """
    Import filters from a TXT file.
    Expected format per line: [category]{phrase}
    Example: [political]{Bas mouth chalana band kar, asli kaam dikha jhatu 💀 bro}
    """
    content = await file.read()
    
    # Remove UTF-8 BOM if present
    if content.startswith(b'\xef\xbb\xbf'):
        content = content[3:]
    
    try:
        text = content.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded")
    
    pattern = re.compile(r'\[([^\]]+)\]\{([^}]+)\}')
    imported_count = 0
    skipped_count = 0
    
    for line_num, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        
        match = pattern.match(line)
        if not match:
            skipped_count += 1
            continue
        
        category = match.group(1).strip()
        phrase = match.group(2).strip()
        
        if not phrase:
            skipped_count += 1
            continue
        
        # Skip duplicates
        existing = db.query(PredefinedFilter).filter(PredefinedFilter.phrase == phrase).first()
        if existing:
            skipped_count += 1
            continue
        
        final_lang = None if language == "auto" else language
        
        new_filter = PredefinedFilter(
            phrase=phrase,
            category=category,
            language=final_lang,
            action="mark_bad",
            is_active=True,
            created_by=user.id
        )
        db.add(new_filter)
        imported_count += 1
    
    db.commit()
    
    # Optional: flash a success message (if you have flash messaging)
    # For now, just redirect
    return RedirectResponse(url="/admin/filters", status_code=302)

@router.get("/predefined-filters", response_class=HTMLResponse)
async def admin_predefined_filters(
    request: Request,
    user=Depends(admin_required),
    db: Session = Depends(get_db)
):
    filters = db.query(PredefinedFilter).order_by(PredefinedFilter.created_at.desc()).all()
    return templates.TemplateResponse(
        "admin/predefined_filters.html",
        {"request": request, "user": user, "filters": filters}
    )

# @router.post("/predefined-filters/import")
# async def import_predefined_filters(
#     file: UploadFile = File(...),
#     column: str = Form("english"),
#     user=Depends(admin_required),
#     db: Session = Depends(get_db)
# ):
#     content = await file.read()
#     try:
#         # Remove BOM if present
#         if content.startswith(b'\xef\xbb\xbf'):
#             content = content[3:]
#         decoded = content.decode('utf-8')
#         import csv
#         import io
#         reader = csv.DictReader(io.StringIO(decoded))
#         column_map = {
#             "english": "English_Comment",
#             "hindi": "Hindi_Comment",
#             "hinglish": "Hinglish_Comment"
#         }
#         target_col = column_map.get(column, "English_Comment")
#         imported = 0
#         for row in reader:
#             phrase = row.get(target_col, "").strip()
#             if not phrase:
#                 continue
#             category = row.get("Category", "").strip()
#             # Skip duplicate phrases
#             existing = db.query(PredefinedFilter).filter(PredefinedFilter.phrase == phrase).first()
#             if existing:
#                 continue
#             filter = PredefinedFilter(
#                 phrase=phrase,
#                 category=category,
#                 action="mark_bad",
#                 is_active=True,
#                 created_by=user.id
#             )
#             db.add(filter)
#             imported += 1
#         db.commit()
#         return RedirectResponse(url="/admin/predefined-filters", status_code=302)
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=f"Error importing file: {str(e)}")

import re
import csv
import io

@router.post("/predefined-filters/import")
async def import_predefined_filters(
    file: UploadFile = File(...),
    column: str = Form("english"),
    user = Depends(admin_required),
    db: Session = Depends(get_db)
):
    content = await file.read()
    
    # Remove UTF-8 BOM if present
    if content.startswith(b'\xef\xbb\xbf'):
        content = content[3:]
    
    try:
        decoded = content.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded")

    # --- Detect format: CSV (has commas and newlines) or TXT ([...]{...}) ---
    lines = decoded.splitlines()
    first_line = lines[0].strip() if lines else ""
    
    # Check if it's a TXT file with pattern [category]{phrase}
    txt_pattern = re.compile(r'^\[[^\]]+\]\{[^}]+\}$')
    is_txt = bool(txt_pattern.match(first_line))
    
    imported = 0
    
    if is_txt:
        # --- TXT format: [category]{phrase} ---
        pattern = re.compile(r'\[([^\]]+)\]\{([^}]+)\}')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            match = pattern.match(line)
            if not match:
                continue
            category = match.group(1).strip()
            phrase = match.group(2).strip()
            if not phrase:
                continue
            # Skip duplicates
            existing = db.query(PredefinedFilter).filter(PredefinedFilter.phrase == phrase).first()
            if existing:
                continue
            filter = PredefinedFilter(
                phrase=phrase,
                category=category,
                action="mark_bad",
                is_active=True,
                created_by=user.id
            )
            db.add(filter)
            imported += 1
    else:
        # --- CSV format (original behavior) ---
        reader = csv.DictReader(io.StringIO(decoded))
        column_map = {
            "english": "English_Comment",
            "hindi": "Hindi_Comment",
            "hinglish": "Hinglish_Comment"
        }
        target_col = column_map.get(column, "English_Comment")
        for row in reader:
            phrase = row.get(target_col, "").strip()
            if not phrase:
                continue
            category = row.get("Category", "").strip()
            existing = db.query(PredefinedFilter).filter(PredefinedFilter.phrase == phrase).first()
            if existing:
                continue
            filter = PredefinedFilter(
                phrase=phrase,
                category=category,
                action="mark_bad",
                is_active=True,
                created_by=user.id
            )
            db.add(filter)
            imported += 1
    
    db.commit()
    return RedirectResponse(url="/admin/predefined-filters", status_code=302)

@router.post("/predefined-filters/add")
async def add_predefined_filter(
    phrase: str = Form(...),
    category: str = Form(None),
    action: str = Form("mark_bad"),
    user=Depends(admin_required),
    db: Session = Depends(get_db)
):
    filter = PredefinedFilter(
        phrase=phrase, category=category, action=action, is_active=True, created_by=user.id
    )
    db.add(filter)
    db.commit()
    return RedirectResponse(url="/admin/predefined-filters", status_code=302)

@router.post("/predefined-filters/{filter_id}/toggle")
async def toggle_predefined_filter(filter_id: int, user=Depends(admin_required), db: Session = Depends(get_db)):
    filter = db.query(PredefinedFilter).get(filter_id)
    if filter:
        filter.is_active = not filter.is_active
        db.commit()
    return RedirectResponse(url="/admin/predefined-filters", status_code=302)

@router.post("/predefined-filters/{filter_id}/delete")
async def delete_predefined_filter(filter_id: int, user=Depends(admin_required), db: Session = Depends(get_db)):
    filter = db.query(PredefinedFilter).get(filter_id)
    if filter:
        db.delete(filter)
        db.commit()
    return RedirectResponse(url="/admin/predefined-filters", status_code=302)

# ---------- Admin Statistics ----------
@router.get("/stats")
async def admin_stats(
    db: Session = Depends(get_db),
    admin_user: User = Depends(admin_required)
):
    # Total comments per user
    user_stats = db.query(
        User.username,
        func.count(Comment.id).label("total_comments")
    ).join(ExtractionJob, ExtractionJob.user_id == User.id)\
     .join(Comment, Comment.extraction_job_id == ExtractionJob.job_id)\
     .group_by(User.id).all()

    # Comments per day
    day_stats = db.query(
        func.date(Comment.created_at).label("day"),
        func.count(Comment.id).label("count")
    ).group_by("day").order_by("day").all()

    # Pending jobs count
    pending_count = db.query(ExtractionJob).filter(ExtractionJob.status == "pending").count()

    return {
        "user_stats": [{"username": u[0], "total": u[1]} for u in user_stats],
        "daily_stats": [{"date": d[0], "count": d[1]} for d in day_stats],
        "pending_jobs": pending_count
    }


# ---------- Send Notification ----------
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

# ... existing imports ...

from app.models.database import Level2Category, Level3Subcategory  # add these imports

# ========== Category Management ==========

@router.get("/categories", response_class=HTMLResponse)
async def admin_categories(
    request: Request,
    user = Depends(admin_required),
    db: Session = Depends(get_db)
):
    """Admin page to manage level2 categories and level3 subcategories."""
    categories = db.query(Level2Category).order_by(Level2Category.order).all()
    subcategories = db.query(Level3Subcategory).order_by(Level3Subcategory.order).all()
    return templates.TemplateResponse(
        "admin/categories.html",
        {
            "request": request,
            "user": user,
            "categories": categories,
            "subcategories": subcategories
        }
    )

@router.post("/categories/add")
async def add_category(
    name: str = Form(...),
    description: str = Form(""),
    order: int = Form(0),
    user = Depends(admin_required),
    db: Session = Depends(get_db)
):
    """Add a new level2 category."""
    existing = db.query(Level2Category).filter(Level2Category.name == name).first()
    if existing:
        return templates.TemplateResponse(
            "admin/categories.html",
            {
                "request": request,
                "user": user,
                "categories": db.query(Level2Category).all(),
                "subcategories": db.query(Level3Subcategory).all(),
                "error": "Category name already exists."
            }
        )
    category = Level2Category(name=name, description=description, order=order)
    db.add(category)
    db.commit()
    return RedirectResponse(url="/admin/categories", status_code=302)

@router.post("/categories/{category_id}/edit")
async def edit_category(
    category_id: int,
    name: str = Form(...),
    description: str = Form(""),
    order: int = Form(0),
    is_active: bool = Form(False),
    user = Depends(admin_required),
    db: Session = Depends(get_db)
):
    category = db.query(Level2Category).filter(Level2Category.id == category_id).first()
    if not category:
        raise HTTPException(404, "Category not found")
    category.name = name
    category.description = description
    category.order = order
    category.is_active = is_active
    db.commit()
    return RedirectResponse(url="/admin/categories", status_code=302)

@router.post("/categories/{category_id}/delete")
async def delete_category(
    category_id: int,
    user = Depends(admin_required),
    db: Session = Depends(get_db)
):
    category = db.query(Level2Category).filter(Level2Category.id == category_id).first()
    if category:
        # Also delete associated subcategories (or set to inactive)
        db.query(Level3Subcategory).filter(Level3Subcategory.category_id == category_id).delete()
        db.delete(category)
        db.commit()
    return RedirectResponse(url="/admin/categories", status_code=302)

# ---------- Subcategories ----------

@router.post("/subcategories/add")
async def add_subcategory(
    name: str = Form(...),
    category_id: int = Form(...),
    description: str = Form(""),
    order: int = Form(0),
    user = Depends(admin_required),
    db: Session = Depends(get_db)
):
    category = db.query(Level2Category).filter(Level2Category.id == category_id).first()
    if not category:
        return templates.TemplateResponse(
            "admin/categories.html",
            {
                "request": request,
                "user": user,
                "categories": db.query(Level2Category).all(),
                "subcategories": db.query(Level3Subcategory).all(),
                "error": "Parent category not found."
            }
        )
    sub = Level3Subcategory(name=name, category_id=category_id, description=description, order=order)
    db.add(sub)
    db.commit()
    return RedirectResponse(url="/admin/categories", status_code=302)

@router.post("/subcategories/{sub_id}/edit")
async def edit_subcategory(
    sub_id: int,
    name: str = Form(...),
    category_id: int = Form(...),
    description: str = Form(""),
    order: int = Form(0),
    is_active: bool = Form(False),
    user = Depends(admin_required),
    db: Session = Depends(get_db)
):
    sub = db.query(Level3Subcategory).filter(Level3Subcategory.id == sub_id).first()
    if not sub:
        raise HTTPException(404, "Subcategory not found")
    sub.name = name
    sub.category_id = category_id
    sub.description = description
    sub.order = order
    sub.is_active = is_active
    db.commit()
    return RedirectResponse(url="/admin/categories", status_code=302)

@router.post("/subcategories/{sub_id}/delete")
async def delete_subcategory(
    sub_id: int,
    user = Depends(admin_required),
    db: Session = Depends(get_db)
):
    sub = db.query(Level3Subcategory).filter(Level3Subcategory.id == sub_id).first()
    if sub:
        db.delete(sub)
        db.commit()
    return RedirectResponse(url="/admin/categories", status_code=302)

# ---------- API endpoints for frontend (to get categories dynamically) ----------
@router.get("/api/categories")
async def get_categories_api(
    db: Session = Depends(get_db),
    user = Depends(get_current_user)  # any authenticated user can fetch
):
    categories = db.query(Level2Category).filter(Level2Category.is_active == True).order_by(Level2Category.order).all()
    return [c.to_dict() for c in categories]

@router.get("/api/categories/{category_id}/subcategories")
async def get_subcategories_api(
    category_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    subcategories = db.query(Level3Subcategory).filter(
        Level3Subcategory.category_id == category_id,
        Level3Subcategory.is_active == True
    ).order_by(Level3Subcategory.order).all()
    return [s.to_dict() for s in subcategories]
# Similarly for editing, deleting, and for subcategories.