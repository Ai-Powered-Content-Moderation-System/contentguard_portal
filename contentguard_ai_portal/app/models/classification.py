# app/models/classification.py

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, Float, ForeignKey, Table
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.database import Base

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    code = Column(Integer, unique=True, nullable=False)
    level = Column(Integer)  # 1, 2, or 3
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    description = Column(Text)
    
    # Category metadata
    color = Column(String(20), default="#06e0d5")
    icon = Column(String(50), default="📝")
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # For sorting
    keywords = Column(JSON, default=[])  # Associated keywords for matching
    
    # Rules and patterns
    patterns = Column(JSON, default=[])  # Regex patterns for matching
    severity = Column(String(20), default="medium")  # low, medium, high, critical
    action_required = Column(String(100), nullable=True)  # review, remove, ignore
    
    # Statistics
    total_comments = Column(Integer, default=0)
    last_used = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    parent = relationship("Category", remote_side=[id], backref="subcategories")
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "level": self.level,
            "parent_id": self.parent_id,
            "description": self.description,
            "color": self.color,
            "icon": self.icon,
            "is_active": self.is_active,
            "priority": self.priority,
            "severity": self.severity,
            "total_comments": self.total_comments
        }

class SubCategory(Base):
    __tablename__ = "subcategories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    code = Column(Integer, unique=True, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"))
    parent_id = Column(Integer, ForeignKey("subcategories.id"), nullable=True)
    
    description = Column(Text)
    examples = Column(JSON, default=[])  # Example comments
    keywords = Column(JSON, default=[])  # Associated keywords
    
    # Severity and rules
    severity_score = Column(Float, default=1.0)  # Multiplier for severity
    requires_immediate_action = Column(Boolean, default=False)
    auto_moderate = Column(Boolean, default=False)  # Auto-remove if true
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    category = relationship("Category", backref="subcategory_list")
    parent = relationship("SubCategory", remote_side=[id], backref="children")

class ClassificationResult(Base):
    __tablename__ = "classification_results"
    
    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(String(100), ForeignKey("comments.comment_id"))
    
    # Model information
    model_name = Column(String(100))
    model_version = Column(String(50))
    model_type = Column(String(50))  # level1, level2, level3
    
    # Classification results
    predicted_category = Column(String(200))
    predicted_code = Column(Integer)
    confidence = Column(Float)
    probabilities = Column(JSON, default={})
    
    # Features used
    features = Column(JSON, default={})
    feature_importance = Column(JSON, default={})
    
    # Processing metadata
    processing_time = Column(Float)  # in seconds
    gpu_used = Column(Boolean, default=False)
    batch_id = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            "comment_id": self.comment_id,
            "model": f"{self.model_name} v{self.model_version}",
            "predicted": self.predicted_category,
            "confidence": self.confidence,
            "processing_time": self.processing_time
        }

# REMOVE THIS ENTIRE CLASS - It's already defined in database.py
# class TrainingData(Base):
#     __tablename__ = "training_data"
#     ...

# Association table for comment-category many-to-many
comment_categories = Table(
    'comment_categories',
    Base.metadata,
    Column('comment_id', Integer, ForeignKey('comments.id')),
    Column('category_id', Integer, ForeignKey('categories.id'))
)