# app/routers/classification.py - Update imports

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Dict

# Change these imports
from app.models.database import get_db, Comment, TrainingData
from app.services.classifier import classifier, LEVEL2_CATEGORIES, LEVEL3_SUBCATEGORIES
from app.utils.helpers import get_current_user
# from fastapi.templating import Jinja2Templates  # Add this line

router = APIRouter()

from fastapi.responses import HTMLResponse

# templates = Jinja2Templates(directory="app/templates")
from app.template import templates

@router.get("/", response_class=HTMLResponse)
async def classification_page(request: Request, user = Depends(get_current_user)):
    return templates.TemplateResponse("classification/index.html", {"request": request, "user": user})
# ... rest of the file remains the same

@router.post("/comment")
async def classify_single_comment(
    request: Request,
    comment_data: Dict,
    user = Depends(get_current_user)
):
    """Classify a single comment"""
    try:
        text = comment_data.get("text", "")
        if not text:
            return JSONResponse({
                "success": False,
                "error": "No text provided"
            })

        result = classifier.classify_comment(text)

        return JSONResponse({
            "success": True,
            "result": result
        })

    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        })

@router.post("/batch")
async def classify_batch_comments(
    request: Request,
    data: Dict,
    user = Depends(get_current_user)
):
    """Classify multiple comments in batch"""
    try:
        comments = data.get("comments", [])
        results = []

        for comment in comments:
            result = classifier.classify_comment(comment.get("text", ""))
            results.append({
                "id": comment.get("id"),
                "text": comment.get("text"),
                "classification": result
            })

        return JSONResponse({
            "success": True,
            "results": results,
            "total": len(results)
        })

    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        })

@router.get("/stats")
async def get_classification_stats(
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get classification statistics"""
    try:
        total = db.query(Comment).count()
        good = db.query(Comment).filter(Comment.level1_category == "good").count()
        bad = db.query(Comment).filter(Comment.level1_category == "bad").count()
        unclassified = db.query(Comment).filter(Comment.level1_category.is_(None)).count()

        # Category breakdown
        categories = {}
        for cat in LEVEL2_CATEGORIES.keys():
            count = db.query(Comment).filter(Comment.level2_category == cat).count()
            if count > 0:
                categories[cat] = count

        return JSONResponse({
            "success": True,
            "stats": {
                "total": total,
                "good": good,
                "bad": bad,
                "unclassified": unclassified,
                "categories": categories,
                "accuracy": (good + bad) / total if total > 0 else 0
            }
        })

    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        })

@router.get("/categories")
async def get_categories():
    """Get all category definitions"""
    return JSONResponse({
        "success": True,
        "level1": ["good", "bad"],
        "level2": list(LEVEL2_CATEGORIES.keys()),
        "level3": list(LEVEL3_SUBCATEGORIES.keys())
    })