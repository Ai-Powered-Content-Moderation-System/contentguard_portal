from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.database import Base

class Comment(Base):
    __tablename__ = "comments"
    
    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(String(100), unique=True, index=True, nullable=False)  # Original YouTube comment ID or generated UUID
    
    # Comment content
    content = Column(Text, nullable=False)  # Encrypted
    content_hash = Column(String(64), index=True)  # For duplicate detection
    content_length = Column(Integer, default=0)
    language = Column(String(10), default="en")  # Detected language
    
    # Author information
    author = Column(String(255))
    author_id = Column(String(100), index=True)
    author_channel_url = Column(String(500))
    author_verified = Column(Boolean, default=False)
    author_subscriber_count = Column(Integer, default=0)
    author_join_date = Column(DateTime, nullable=True)
    author_video_count = Column(Integer, default=0)
    
    # Video information
    video_id = Column(String(100), index=True)
    video_title = Column(String(500))
    video_url = Column(String(500))
    video_channel = Column(String(255))
    video_channel_id = Column(String(100))
    video_published_at = Column(DateTime, nullable=True)
    video_category = Column(String(100))
    video_duration = Column(Integer, default=0)  # in seconds
    video_view_count = Column(Integer, default=0)
    
    # Comment metadata
    published_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    like_count = Column(Integer, default=0)
    reply_count = Column(Integer, default=0)
    is_reply = Column(Boolean, default=False)
    parent_id = Column(String(100), nullable=True)
    parent_author = Column(String(255), nullable=True)
    
    # Classification Results - Level 1
    level1_category = Column(String(50))  # good/bad
    level1_confidence = Column(Float, default=0.0)
    level1_scores = Column(JSON, default={})
    level1_model_version = Column(String(50))
    
    # Classification Results - Level 2 (Main Categories)
    level2_category = Column(String(100))  # Harassment, Hate Speech, etc.
    level2_confidence = Column(Float, default=0.0)
    level2_scores = Column(JSON, default={})
    level2_model_version = Column(String(50))
    
    # Classification Results - Level 3 (Sub-categories)
    level3_subcategory = Column(String(200))
    level3_confidence = Column(Float, default=0.0)
    level3_scores = Column(JSON, default={})
    level3_model_version = Column(String(50))
    
    # Overall classification
    confidence_scores = Column(JSON, default={})
    toxicity_score = Column(Float, default=0.0)  # 0-1 scale
    sentiment_score = Column(Float, default=0.0)  # -1 to 1
    urgency_score = Column(Float, default=0.0)  # 0-1 scale
    
    # AI Analysis
    keywords = Column(JSON, default=[])  # Extracted keywords
    entities = Column(JSON, default=[])  # Named entities
    sentiment = Column(String(20))  # positive, negative, neutral
    emotion = Column(String(50))  # anger, joy, sadness, etc.
    spam_probability = Column(Float, default=0.0)
    
    # Moderation status
    is_reviewed = Column(Boolean, default=False)
    reviewed_by = Column(String(255), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    is_approved = Column(Boolean, default=False)
    is_flagged = Column(Boolean, default=False)
    flag_reason = Column(String(500), nullable=True)
    flag_count = Column(Integer, default=0)
    
    # User feedback
    user_feedback = Column(JSON, default=[])  # List of user feedback on classification
    correction_history = Column(JSON, default=[])  # History of manual corrections
    
    # Tags and categories
    tags = Column(Text, default="")  # Comma-separated tags
    custom_categories = Column(JSON, default=[])  # User-defined categories
    
    # Source information
    source = Column(String(50))  # youtube, manual_upload, api, etc.
    source_file = Column(String(500))  # Original CSV file
    source_level = Column(Integer)  # 1, 2, or 3
    extraction_job_id = Column(String(100), nullable=True)
    batch_id = Column(String(100), nullable=True)  # For batch processing
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    exported_at = Column(DateTime, nullable=True)
    
    # Relationships
    training_data = relationship("TrainingData", back_populates="comment")
    
    def to_dict(self):
        """Convert comment to dictionary"""
        return {
            "id": self.id,
            "comment_id": self.comment_id,
            "content": self.content,
            "author": self.author,
            "author_id": self.author_id,
            "video_id": self.video_id,
            "video_title": self.video_title,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "like_count": self.like_count,
            "level1": {
                "category": self.level1_category,
                "confidence": self.level1_confidence
            },
            "level2": {
                "category": self.level2_category,
                "confidence": self.level2_confidence
            },
            "level3": {
                "category": self.level3_subcategory,
                "confidence": self.level3_confidence
            },
            "toxicity_score": self.toxicity_score,
            "sentiment": self.sentiment,
            "is_reviewed": self.is_reviewed,
            "is_approved": self.is_approved,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    def get_classification_summary(self):
        """Get summary of classification results"""
        return {
            "level1": f"{self.level1_category} ({self.level1_confidence:.2f})",
            "level2": f"{self.level2_category} ({self.level2_confidence:.2f})" if self.level2_category else "N/A",
            "level3": f"{self.level3_subcategory} ({self.level3_confidence:.2f})" if self.level3_subcategory else "N/A",
            "toxicity": f"{self.toxicity_score:.2f}",
            "sentiment": self.sentiment
        }
    
    def is_bad(self):
        """Check if comment is classified as bad"""
        return self.level1_category == "bad"
    
    def needs_review(self):
        """Check if comment needs human review"""
        return (not self.is_reviewed and 
                (self.level1_confidence < 0.8 or 
                 self.toxicity_score > 0.5))