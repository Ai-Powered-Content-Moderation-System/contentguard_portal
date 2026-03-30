# app/models/extraction.py

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from app.models.database import Base, engine
from app.models.database import ExtractionJob

class ExtractionPattern(Base):
    __tablename__ = "extraction_patterns"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    pattern_format = Column(String(500), nullable=False)
    regex_pattern = Column(String(500), nullable=False)
    description = Column(Text)

    # Pattern components
    tag_placeholder = Column(String(50), default="tag")
    comment_placeholder = Column(String(50), default="comment")
    delimiter = Column(String(50), nullable=True)
    requires_tag = Column(Boolean, default=True)

    # Pattern testing
    test_string = Column(Text, nullable=True)
    test_result = Column(JSON, nullable=True)

    # Usage statistics
    is_active = Column(Boolean, default=False)
    usage_count = Column(Integer, default=0)
    last_used = Column(DateTime, nullable=True)
    success_rate = Column(Float, default=0.0)

    # Metadata
    created_by = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "pattern": self.pattern_format,
            "regex": self.regex_pattern,
            "description": self.description,
            "is_active": self.is_active,
            "usage_count": self.usage_count,
            "success_rate": self.success_rate,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    def increment_usage(self, success: bool = True):
        """Increment usage count and update success rate"""
        self.usage_count += 1
        if success:
            self.success_rate = (self.success_rate * (self.usage_count - 1) + 1) / self.usage_count
        else:
            self.success_rate = (self.success_rate * (self.usage_count - 1)) / self.usage_count
        self.last_used = datetime.utcnow()


class ExtractedData(Base):
    __tablename__ = "extracted_data"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(100), ForeignKey("extraction_jobs.job_id"))
    comment_id = Column(String(100), ForeignKey("comments.comment_id"))

    # Raw extracted data
    raw_data = Column(JSON, default={})
    extracted_at = Column(DateTime, default=datetime.utcnow)

    # Extraction metadata
    extraction_time = Column(Float)  # in seconds
    extraction_method = Column(String(50))
    pattern_used = Column(String(255), nullable=True)

    # Quality metrics
    data_quality = Column(Float, default=1.0)  # 0-1 scale
    missing_fields = Column(JSON, default=[])
    validation_errors = Column(JSON, default=[])

    # Relationships
    # Note: We don't define relationship here to avoid circular imports

# Function to create extraction tables
def init_extraction_tables():
    Base.metadata.create_all(bind=engine, tables=[
        ExtractionPattern.__table__,
        ExtractionJob.__table__,
        ExtractedData.__table__
    ])