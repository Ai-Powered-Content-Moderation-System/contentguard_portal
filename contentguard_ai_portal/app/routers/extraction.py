from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from sqlalchemy.orm import Session
from typing import Optional
import uuid
import re
from datetime import datetime
from sqlalchemy import func

from app.models.database import get_db, Comment, ExtractionJob, User,Notification
from app.models.extraction import ExtractionPattern
from app.services.youtube_extractor import youtube_extractor
from app.services.classifier import classifier
from app.services.encryption import decrypt_content
from app.utils.helpers import get_current_user, admin_required
from app.template import templates
from pydantic import BaseModel

router = APIRouter()


# ----- Pydantic model for extraction request -----
class ExtractionRequest(BaseModel):
    url: str
    max_comments: int = 500


# ----- User Extraction Dashboard -----
@router.get("/", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def extraction_page(
    request: Request,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Extraction dashboard – different view for admin vs regular user"""
    if user.is_admin:
        # Admin: show full extraction interface with all jobs
        jobs = db.query(ExtractionJob).order_by(ExtractionJob.requested_at.desc()).all()
        total_jobs = len(jobs)
        total_extracted = sum(job.comment_count or 0 for job in jobs)

        # Prepare job list with computed fields to match the template
        recent_jobs = []
        for job in jobs:
            source_type = "youtube" if job.video_url else "file"
            progress = 100 if job.status == "completed" else 0
            recent_jobs.append({
                "job_id": job.job_id,
                "source_type": source_type,
                "status": job.status,
                "progress": progress,
                "extracted_comments": job.comment_count,
                "total_comments": job.comment_count,
                "created_at": job.requested_at,
                "output_file": job.csv_file_path,
            })

        patterns = db.query(ExtractionPattern).filter(ExtractionPattern.is_active == True).all()

        return templates.TemplateResponse(
            "extraction/index_admin.html",
            {
                "request": request,
                "user": user,
                "recent_jobs": recent_jobs,
                "total_jobs": total_jobs,
                "total_extracted": total_extracted,
                "patterns": patterns
            }
        )
    else:
        # Regular user: show only their own requests
        jobs = db.query(ExtractionJob).filter(ExtractionJob.user_id == user.id)\
                .order_by(ExtractionJob.requested_at.desc()).all()
        total_jobs = len(jobs)
        total_extracted = sum(job.comment_count or 0 for job in jobs)
        return templates.TemplateResponse(
            "extraction/index.html",
            {
                "request": request,
                "user": user,
                "recent_jobs": jobs,
                "total_jobs": total_jobs,
                "total_extracted": total_extracted
            }
        )

from app.utils.helpers import extract_youtube_video_id

@router.post("/admin-youtube")
async def admin_youtube_extract(
    request: Request,
    background_tasks: BackgroundTasks,
    url: str = Form(...),
    max_comments: int = Form(500),
    include_replies: bool = Form(True),
    apply_classification: bool = Form(True),
    admin_user: User = Depends(admin_required),  # only admin
    db: Session = Depends(get_db)
):
    """Admin-only: extract comments directly using yt-dlp."""
    # Create job record (optional – you may want to create a job for this)
    job_id = str(uuid.uuid4())
    job = ExtractionJob(
        job_id=job_id,
        user_id=admin_user.id,
        video_url=url,
        # video_id will be set later
        max_comments=max_comments,
        status="processing"
    )
    db.add(job)
    db.commit()

    # Start extraction in background
    background_tasks.add_task(
        process_youtube_extraction_staged,
        job.job_id,
        url,
        max_comments,
        include_replies,
        apply_classification,
        admin_user.username
    )

    return JSONResponse({
        "success": True,
        "message": "Extraction started",
        "job_id": job_id
    })
# ----- Submit a new extraction request (JSON) -----
@router.post("/submit")
async def submit_extraction_job(
    req: ExtractionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Extract video ID from URL
    try:
        video_id = extract_youtube_video_id(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Check if a job already exists for this video
    existing = db.query(ExtractionJob).filter(ExtractionJob.video_id == video_id).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"A job for this video already exists (status: {existing.status})"
        )

    # Create new job
    job_id = str(uuid.uuid4())
    new_job = ExtractionJob(
        job_id=job_id,
        user_id=current_user.id,
        video_url=req.url,
        video_id=video_id,
        max_comments=req.max_comments,
        status="pending"
    )
    db.add(new_job)
    print("=== Creating notifications for admins ===")
    admins = db.query(User).filter(User.is_admin == True).all()
    print(f"Found {len(admins)} admins")
    for admin in admins:
        notif = Notification(
            user_id=admin.id,
            message=f"New extraction request from {current_user.username} for video: {req.url}",
            is_read=False
        )
        db.add(notif)
    print(f"Added {len(admins)} notifications")
    db.commit()
    db.refresh(new_job)

    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Your extraction request has been submitted. The admin will process it soon."
    }


# ----- List user's jobs (JSON) -----
@router.get("/my-jobs")
async def list_my_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    jobs = db.query(ExtractionJob).filter(ExtractionJob.user_id == current_user.id)\
            .order_by(ExtractionJob.requested_at.desc()).all()
    return [{
        "job_id": j.job_id,
        "video_url": j.video_url,
        "video_title": j.video_title,
        "status": j.status,
        "requested_at": j.requested_at,
        "completed_at": j.completed_at,
        "comment_count": j.comment_count
    } for j in jobs]


# ----- View comments for a specific job -----
@router.get("/jobs/{job_id}/comments", response_class=HTMLResponse)
async def view_job_comments(
    request: Request,
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = db.query(ExtractionJob).filter(ExtractionJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    comments = db.query(Comment).filter(Comment.extraction_job_id == job_id).all()
    # Decrypt content for display (if stored encrypted)
    for c in comments:
        try:
            c.content = decrypt_content(c.content)
        except:
            pass

    return templates.TemplateResponse(
        "extraction/job_comments.html",
        {
            "request": request,
            "user": current_user,
            "job": job,
            "comments": comments
        }
    )


# ----- (Optional) List all jobs (admin can still use) -----
@router.get("/jobs")
async def list_jobs(
    page: int = 1,
    per_page: int = 20,
    status: Optional[str] = None,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all extraction jobs (for admin or debugging)."""
    query = db.query(ExtractionJob)
    if status:
        query = query.filter(ExtractionJob.status == status)

    total = query.count()
    jobs = query.order_by(ExtractionJob.requested_at.desc())\
                .offset((page - 1) * per_page)\
                .limit(per_page)\
                .all()

    return JSONResponse({
        "success": True,
        "jobs": [j.to_dict() for j in jobs],
        "total": total,
        "page": page,
        "total_pages": (total + per_page - 1) // per_page
    })


# ----- (Optional) Get job status by ID -----
@router.get("/jobs/{job_id}/status")
async def get_job_status(
    job_id: str,
    db: Session = Depends(get_db)
):
    job = db.query(ExtractionJob).filter(ExtractionJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse({
        "success": True,
        "status": job.status,
        "progress": 0,               # not used in this model
        "extracted": job.comment_count,
        "total": job.comment_count,
        "error": job.error_message if job.status == "failed" else None,
        "video_title": job.video_title
    })

@router.get("/jobs/{job_id}/comments-ids")
async def get_job_comment_ids(job_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(ExtractionJob).filter(ExtractionJob.job_id == job_id).first()
    if not job or (job.user_id != user.id and not user.is_admin):
        raise HTTPException(403, "Not authorized")
    comment_ids = [c.comment_id for c in db.query(Comment.comment_id).filter(Comment.extraction_job_id == job_id).all()]
    return {"comment_ids": comment_ids}