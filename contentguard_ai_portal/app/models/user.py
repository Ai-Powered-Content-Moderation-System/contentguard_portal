# # v2
# # app/models/user.py

# from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON
# from datetime import datetime
# from app.models.database import Base, engine

# class User(Base):
#     __tablename__ = "users"
#     notifications = relationship("Notification", back_populates="user")
#     extraction_jobs = relationship("ExtractionJob", back_populates="user")
#     id = Column(Integer, primary_key=True, index=True)
#     username = Column(String(255), unique=True, nullable=False, index=True)
#     email = Column(String(255), unique=True, nullable=True, index=True)
#     password = Column(String(255), nullable=False)
#     name = Column(String(255))

#     # User settings and preferences
#     is_admin = Column(Boolean, default=False)
#     is_active = Column(Boolean, default=True)
#     is_verified = Column(Boolean, default=False)
#     theme_preference = Column(String(50), default="modern")

#     # User metadata
#     profile_picture = Column(String(500), nullable=True)
#     bio = Column(Text, nullable=True)
#     department = Column(String(255), nullable=True)
#     designation = Column(String(255), nullable=True)

#     # Permissions and roles
#     roles = Column(JSON, default=[])  # List of roles
#     permissions = Column(JSON, default=[])  # List of permissions

#     extraction_jobs = relationship("ExtractionJob", back_populates="user")
#     # Tracked comments and activity
#     comment_ids = Column(Text, default="[]")  # JSON array of comment IDs
#     reviewed_comments = Column(JSON, default=[])  # Comments reviewed by user
#     extracted_jobs = Column(JSON, default=[])  # Extraction jobs created by user

#     # Account statistics
#     total_logins = Column(Integer, default=0)
#     last_login_ip = Column(String(50), nullable=True)
#     last_login_user_agent = Column(Text, nullable=True)

#     # Timestamps
#     created_at = Column(DateTime, default=datetime.utcnow)
#     updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
#     last_login = Column(DateTime, nullable=True)
#     last_activity = Column(DateTime, nullable=True)
#     password_changed_at = Column(DateTime, nullable=True)

#     # Account recovery
#     reset_password_token = Column(String(255), nullable=True)
#     reset_password_expires = Column(DateTime, nullable=True)
#     email_verification_token = Column(String(255), nullable=True)
#     email_verified_at = Column(DateTime, nullable=True)

#     # Two factor authentication
#     two_factor_enabled = Column(Boolean, default=False)
#     two_factor_secret = Column(String(255), nullable=True)
#     backup_codes = Column(JSON, default=[])

#     # API access
#     api_key = Column(String(255), nullable=True, unique=True)
#     api_key_created_at = Column(DateTime, nullable=True)
#     api_key_expires = Column(DateTime, nullable=True)

#     def to_dict(self):
#         """Convert user object to dictionary"""
#         return {
#             "id": self.id,
#             "username": self.username,
#             "email": self.email,
#             "name": self.name,
#             "is_admin": self.is_admin,
#             "is_active": self.is_active,
#             "is_verified": self.is_verified,
#             "theme_preference": self.theme_preference,
#             "department": self.department,
#             "designation": self.designation,
#             "roles": self.roles,
#             "permissions": self.permissions,
#             "total_logins": self.total_logins,
#             "created_at": self.created_at.isoformat() if self.created_at else None,
#             "last_login": self.last_login.isoformat() if self.last_login else None,
#             "last_activity": self.last_activity.isoformat() if self.last_activity else None
#         }

#     def has_permission(self, permission: str) -> bool:
#         """Check if user has specific permission"""
#         if self.is_admin:
#             return True
#         return permission in self.permissions

#     def has_role(self, role: str) -> bool:
#         """Check if user has specific role"""
#         return role in self.roles

#     def update_last_login(self, ip: str = None, user_agent: str = None):
#         """Update last login information"""
#         self.last_login = datetime.utcnow()
#         self.last_activity = datetime.utcnow()
#         self.total_logins += 1
#         if ip:
#             self.last_login_ip = ip
#         if user_agent:
#             self.last_login_user_agent = user_agent

#     def add_comment_id(self, comment_id: int):
#         """Add comment ID to user's list"""
#         import json
#         current_ids = json.loads(self.comment_ids or '[]')
#         if comment_id not in current_ids:
#             current_ids.append(comment_id)
#             self.comment_ids = json.dumps(current_ids)

#     def get_comment_ids(self):
#         """Get list of comment IDs"""
#         import json
#         return json.loads(self.comment_ids or '[]')

# # Function to create MySQL tables
# # def init_mysql_tables():
# #     """Create MySQL tables"""
# #     Base.metadata.create_all(bind=mysql_engine, tables=[User.__table__])
# # from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON
# # from sqlalchemy.orm import relationship
# # from datetime import datetime
# # from app.models.database import Base

# # class User(Base):
# #     __tablename__ = "users"

# #     id = Column(Integer, primary_key=True, index=True)
# #     username = Column(String(255), unique=True, nullable=False, index=True)
# #     email = Column(String(255), unique=True, nullable=True, index=True)
# #     password = Column(String(255), nullable=False)
# #     name = Column(String(255))

# #     # User settings and preferences
# #     is_admin = Column(Boolean, default=False)
# #     is_active = Column(Boolean, default=True)
# #     is_verified = Column(Boolean, default=False)
# #     theme_preference = Column(String(50), default="modern")

# #     # User metadata
# #     profile_picture = Column(String(500), nullable=True)
# #     bio = Column(Text, nullable=True)
# #     department = Column(String(255), nullable=True)
# #     designation = Column(String(255), nullable=True)

# #     # Permissions and roles
# #     roles = Column(JSON, default=[])  # List of roles
# #     permissions = Column(JSON, default=[])  # List of permissions

# #     # Tracked comments and activity
# #     comment_ids = Column(Text, default="[]")  # JSON array of comment IDs
# #     reviewed_comments = Column(JSON, default=[])  # Comments reviewed by user
# #     extracted_jobs = Column(JSON, default=[])  # Extraction jobs created by user

# #     # Account statistics
# #     total_logins = Column(Integer, default=0)
# #     last_login_ip = Column(String(50), nullable=True)
# #     last_login_user_agent = Column(Text, nullable=True)

# #     # Timestamps
# #     created_at = Column(DateTime, default=datetime.utcnow)
# #     updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
# #     last_login = Column(DateTime, nullable=True)
# #     last_activity = Column(DateTime, nullable=True)
# #     password_changed_at = Column(DateTime, nullable=True)

# #     # Account recovery
# #     reset_password_token = Column(String(255), nullable=True)
# #     reset_password_expires = Column(DateTime, nullable=True)
# #     email_verification_token = Column(String(255), nullable=True)
# #     email_verified_at = Column(DateTime, nullable=True)

# #     # Two factor authentication
# #     two_factor_enabled = Column(Boolean, default=False)
# #     two_factor_secret = Column(String(255), nullable=True)
# #     backup_codes = Column(JSON, default=[])

# #     # API access
# #     api_key = Column(String(255), nullable=True, unique=True)
# #     api_key_created_at = Column(DateTime, nullable=True)
# #     api_key_expires = Column(DateTime, nullable=True)

# #     def to_dict(self):
# #         """Convert user object to dictionary"""
# #         return {
# #             "id": self.id,
# #             "username": self.username,
# #             "email": self.email,
# #             "name": self.name,
# #             "is_admin": self.is_admin,
# #             "is_active": self.is_active,
# #             "is_verified": self.is_verified,
# #             "theme_preference": self.theme_preference,
# #             "department": self.department,
# #             "designation": self.designation,
# #             "roles": self.roles,
# #             "permissions": self.permissions,
# #             "total_logins": self.total_logins,
# #             "created_at": self.created_at.isoformat() if self.created_at else None,
# #             "last_login": self.last_login.isoformat() if self.last_login else None,
# #             "last_activity": self.last_activity.isoformat() if self.last_activity else None
# #         }

# #     def has_permission(self, permission: str) -> bool:
# #         """Check if user has specific permission"""
# #         if self.is_admin:
# #             return True
# #         return permission in self.permissions

# #     def has_role(self, role: str) -> bool:
# #         """Check if user has specific role"""
# #         return role in self.roles

# #     def update_last_login(self, ip: str = None, user_agent: str = None):
# #         """Update last login information"""
# #         self.last_login = datetime.utcnow()
# #         self.last_activity = datetime.utcnow()
# #         self.total_logins += 1
# #         if ip:
# #             self.last_login_ip = ip
# #         if user_agent:
# #             self.last_login_user_agent = user_agent

# #     def add_comment_id(self, comment_id: int):
# #         """Add comment ID to user's list"""
# #         import json
# #         current_ids = json.loads(self.comment_ids or '[]')
# #         if comment_id not in current_ids:
# #             current_ids.append(comment_id)
# #             self.comment_ids = json.dumps(current_ids)

# #     def get_comment_ids(self):
# #         """Get list of comment IDs"""
# #         import json
# #         return json.loads(self.comment_ids or '[]')