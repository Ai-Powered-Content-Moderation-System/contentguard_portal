# app/models/database.py

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, JSON, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from app.config import settings

# Single SQLite engine
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# ---------- User Model ----------
class User(Base):
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    password = Column(String(255), nullable=False)
    name = Column(String(255))
    extraction_jobs = relationship("ExtractionJob", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    # User settings and preferences
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    theme_preference = Column(String(50), default="modern")

    # User metadata
    profile_picture = Column(String(500), nullable=True)
    bio = Column(Text, nullable=True)
    department = Column(String(255), nullable=True)
    designation = Column(String(255), nullable=True)

    # Permissions and roles
    roles = Column(JSON, default=[])
    permissions = Column(JSON, default=[])

    # Tracked comments and activity
    comment_ids = Column(Text, default="[]")  # JSON array of comment IDs
    reviewed_comments = Column(JSON, default=[])
    extracted_jobs = Column(JSON, default=[])

    # Account statistics
    total_logins = Column(Integer, default=0)
    last_login_ip = Column(String(50), nullable=True)
    last_login_user_agent = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    last_activity = Column(DateTime, nullable=True)
    password_changed_at = Column(DateTime, nullable=True)

    # Account recovery
    reset_password_token = Column(String(255), nullable=True)
    reset_password_expires = Column(DateTime, nullable=True)
    email_verification_token = Column(String(255), nullable=True)
    email_verified_at = Column(DateTime, nullable=True)

    # Two factor authentication
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String(255), nullable=True)
    backup_codes = Column(JSON, default=[])

    # API access
    api_key = Column(String(255), nullable=True, unique=True)
    api_key_created_at = Column(DateTime, nullable=True)
    api_key_expires = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "name": self.name,
            "is_admin": self.is_admin,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "theme_preference": self.theme_preference,
            "department": self.department,
            "designation": self.designation,
            "roles": self.roles,
            "permissions": self.permissions,
            "total_logins": self.total_logins,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None
        }

    def has_permission(self, permission: str) -> bool:
        if self.is_admin:
            return True
        return permission in self.permissions

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def update_last_login(self, ip: str = None, user_agent: str = None):
        self.last_login = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.total_logins += 1
        if ip:
            self.last_login_ip = ip
        if user_agent:
            self.last_login_user_agent = user_agent

    def add_comment_id(self, comment_id: int):
        import json
        current_ids = json.loads(self.comment_ids or '[]')
        if comment_id not in current_ids:
            current_ids.append(comment_id)
            self.comment_ids = json.dumps(current_ids)

    def get_comment_ids(self):
        import json
        return json.loads(self.comment_ids or '[]')


# ---------- Comment Model ----------
class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(String(100), unique=True, index=True)
    content = Column(Text, nullable=False)          # Encrypted
    content_hash = Column(String(64), index=True)
    content_length = Column(Integer, default=0)
    author = Column(String(255))
    author_id = Column(String(100), index=True)

    # Video information
    video_id = Column(String(100), index=True)
    video_title = Column(String(500))
    video_url = Column(String(500))
    video_channel = Column(String(255))
    published_at = Column(DateTime)
    like_count = Column(Integer, default=0)
    reply_count = Column(Integer, default=0)
    is_reply = Column(Boolean, default=False)
    parent_id = Column(String(100), nullable=True)

    # Classification Results
    level1_category = Column(String(50))
    level1_confidence = Column(Float, default=0.0)
    level2_category = Column(String(100))
    level2_confidence = Column(Float, default=0.0)
    level3_subcategory = Column(String(200))
    level3_confidence = Column(Float, default=0.0)
    confidence_scores = Column(JSON, default={})

    # Metadata
    is_reviewed = Column(Boolean, default=False)
    reviewed_by = Column(String(255), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    is_approved = Column(Boolean, default=False)
    tags = Column(Text, default="")
    source = Column(String(50))
    source_file = Column(String(500))
    source_level = Column(Integer)
    extraction_job_id = Column(String(100), nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------- Training Data ----------
class TrainingData(Base):
    __tablename__ = "training_data"

    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(String(100), ForeignKey("comments.comment_id"))
    content = Column(Text)
    level1_category = Column(String(50))
    level2_category = Column(String(100))
    level3_subcategory = Column(String(200))
    is_verified = Column(Boolean, default=False)
    verified_by = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

    comment = relationship("Comment", foreign_keys=[comment_id])



from sqlalchemy import ForeignKey, Integer, String, DateTime, Text, JSON, Float, Boolean
from sqlalchemy.orm import relationship

class ExtractionJob(Base):
    __tablename__ = "extraction_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(100), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)   # link to user

    
    # Video info
    video_url = Column(String(500), nullable=False)
    video_id = Column(String(100), index=True, nullable=False)         # extracted from URL
    video_title = Column(String(500), nullable=True)
    max_comments = Column(Integer, default=500)

    # Status fields
    status = Column(String(50), default="pending")      # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)
    requested_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # CSV upload
    csv_file_path = Column(String(500), nullable=True)  # path where uploaded CSV is stored (optional)

    # Statistics
    comment_count = Column(Integer, default=0)
    good_count = Column(Integer, default=0)
    bad_count = Column(Integer, default=0)

    def to_dict(self):
        return {
            "job_id": self.job_id,
            "video_title": self.video_title,
            "video_url": self.video_url,
            "status": self.status,
            "progress": 0,  # We don't have progress in this simplified model; keep 0 or remove
            "total": self.comment_count,
            "extracted": self.comment_count,
            "good": self.good_count,
            "bad": self.bad_count,
            "created_at": self.requested_at.isoformat() if self.requested_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "output_file": self.csv_file_path
        }

    # Relationship back to User
    user = relationship("User", back_populates="extraction_jobs")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="notifications")


class Level2Category(Base):
    __tablename__ = "level2_categories"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "is_active": self.is_active,
            "order": self.order,
        }

class Level3Subcategory(Base):
    __tablename__ = "level3_subcategories"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    category_id = Column(Integer, ForeignKey("level2_categories.id"))
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # relationship
    category = relationship("Level2Category", backref="subcategories")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "category_id": self.category_id,
            "description": self.description,
            "is_active": self.is_active,
            "order": self.order,
        }


class PredefinedFilter(Base):
    __tablename__ = "predefined_filters"
    id = Column(Integer, primary_key=True)
    phrase = Column(String(500), nullable=False)
    category = Column(String(100), nullable=True)
    action = Column(String(50), default="mark_bad")
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    language = Column(String(20), nullable=True)
    creator = relationship("User")

class CustomFilter(Base):
    __tablename__ = "custom_filters"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    phrase = Column(String(500), nullable=False)
    category = Column(String(100), nullable=True)
    action = Column(String(50), default="mark_bad")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


import logging
from sqlalchemy import inspect

logger = logging.getLogger(__name__)

def init_db():
    """Create all tables in SQLite"""
    logger.info(f"Initializing database at {engine.url}")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Base.metadata.create_all() completed.")
    except Exception as e:
        logger.error(f"Error during create_all: {e}")
        raise

    # Optional: inspect tables after creation
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    logger.info(f"Tables after create_all: {tables}")


# ---------- Dependency ----------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()