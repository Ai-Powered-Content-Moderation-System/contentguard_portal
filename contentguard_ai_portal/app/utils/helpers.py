# app/utils/helpers.py - Update imports and add missing functions
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.templating import Jinja2Templates
from typing import Optional, Dict, Any
import jwt
from datetime import datetime, timedelta
import re
import secrets
import string
import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from functools import wraps
from fuzzywuzzy import fuzz

from app.config import settings
from app.models.database import get_db
from app.models.database import User ,Notification # Change this import

# JWT Security
security = HTTPBearer(auto_error=False)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current user from token (checks both headers and cookies)"""
    token = None

    # Try to get token from Authorization header first
    if credentials:
        token = credentials.credentials

    # If no header token, try to get from cookie
    if not token:
        cookie_token = request.cookies.get("access_token")
        if cookie_token and cookie_token.startswith("Bearer "):
            token = cookie_token[7:]

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify token
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=401,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="User is deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current user from cookie (for template views) - returns None if not authenticated"""
    token = request.cookies.get("access_token")
    if token and token.startswith("Bearer "):
        token = token[7:]
        payload = verify_token(token)
        if payload:
            username = payload.get("sub")
            if username:
                user = db.query(User).filter(User.username == username).first()
                if user and user.is_active:
                    return user
    return None

def admin_required(user: User = Depends(get_current_user)) -> User:
    """Check if user is admin"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user

def get_password_hash(password: str) -> str:
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def generate_password(length: int = 8) -> str:
    """Generate random password"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_username(name: str) -> str:
    """Generate unique username from name"""
    first_name = name.split()[0].lower()
    random_str = ''.join(secrets.choice(string.ascii_lowercase) for _ in range(6))
    random_num = str(secrets.randbelow(1000)).zfill(3)
    return f"{first_name}.{random_str}{random_num}"

def check_duplicate(new_entry: str, entries_list: List[str], threshold: int = 90) -> bool:
    """Check for duplicate entries using fuzzy matching"""
    for entry in entries_list:
        if fuzz.ratio(new_entry, entry) > threshold:
            return True
    return False

def pattern_to_regex(user_pattern: str) -> str:
    """
    Convert user-friendly pattern to regex
    Examples:
        [tag]{comment} -> r'\[(.*?)\]\s*\{(.*?)\}'
        [tag]:comment -> r'\[(.*?)\]:\s*(.*)'
    """
    # Escape special regex characters
    special_chars = ['.', '^', '$', '*', '+', '?', '|', '\\']
    regex = user_pattern
    for char in special_chars:
        regex = regex.replace(char, '\\' + char)

    # Replace placeholders
    placeholders = {
        r'\[tag\]': r'\[(.*?)\]',
        r'{tag}': r'\{(.*?)\}',
        r'<tag>': r'<(.*?)>',
        r'\[comment\]': r'\[(.*?)\]',
        r'{comment}': r'\{(.*?)\}',
        r'comment': r'(.*?)',
        r'tag': r'(.*?)'
    }

    for ph, pattern in placeholders.items():
        regex = regex.replace(ph, pattern)

    # Add optional whitespace
    regex = regex.replace(r'\]', r'\]\\s*')
    regex = regex.replace(r'\}', r'\}\\s*')

    return regex

def validate_regex(pattern: str) -> Tuple[bool, str]:
    """Validate if regex pattern is valid"""
    try:
        re.compile(pattern)
        return True, "Valid regex pattern"
    except re.error as e:
        return False, f"Invalid regex: {str(e)}"

def format_datetime(dt: datetime, format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format datetime object"""
    if dt:
        return dt.strftime(format)
    return ""

def sanitize_input(text: str) -> str:
    """Sanitize user input"""
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove extra whitespace
    text = ' '.join(text.split())
    return text

def extract_mentions(text: str) -> List[str]:
    """Extract @mentions from text"""
    return re.findall(r'@(\w+)', text)

def extract_hashtags(text: str) -> List[str]:
    """Extract #hashtags from text"""
    return re.findall(r'#(\w+)', text)

def extract_urls(text: str) -> List[str]:
    """Extract URLs from text"""
    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[/\w\.-]*(?:\?[\w=&]*)?'
    return re.findall(url_pattern, text)

def calculate_toxicity_score(classification_result: Dict) -> float:
    """Calculate overall toxicity score from classification"""
    score = 0.0
    weights = {
        'level1': 0.3,
        'level2': 0.4,
        'level3': 0.3
    }

    if classification_result.get('level1', {}).get('category') == 'bad':
        score += weights['level1'] * classification_result.get('level1', {}).get('confidence', 0)

    level2_scores = classification_result.get('level2', {}).get('scores', {})
    if level2_scores:
        max_score = max(level2_scores.values())
        score += weights['level2'] * max_score

    level3_scores = classification_result.get('level3', {}).get('scores', {})
    if level3_scores:
        max_score = max(level3_scores.values())
        score += weights['level3'] * max_score

    return min(score, 1.0)

def paginate(query, page: int = 1, per_page: int = 20):
    """Paginate SQLAlchemy query"""
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return {
        'items': items,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page
    }

import re

def extract_youtube_video_id(url: str) -> str:
    """
    Extract YouTube video ID from various URL formats:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://youtu.be/VIDEO_ID?si=...
    - https://www.youtube.com/shorts/VIDEO_ID
    - https://m.youtube.com/shorts/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    """
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
        r'(?:youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',  # explicit shorts
        r'(?:youtu\.be/)([a-zA-Z0-9_-]{11})'            # youtu.be
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError("Invalid YouTube URL – could not extract video ID")

def create_admin_user():
    """Create admin user if it doesn't exist"""
    from app.models.database import get_db
    from app.models.database import User

    db = next(get_db())

    # Check if admin exists
    admin = db.query(User).filter(User.username == "Admin").first()

    if not admin:
        # Create admin user
        admin_user = User(
            username="Admin",
            password=get_password_hash("Admin@123654123"),
            name="System Administrator",
            email="admin@contentguard.ai",
            is_admin=True,
            is_verified=True
        )
        db.add(admin_user)
        db.commit()
        print("✅ Admin user created - Username: admin, Password: Admin@123")
    else:
        print("✅ Admin user already exists")

    db.close()


def create_test_user():
    """Create a test user with username 'test' and password 'test@123' if it doesn't exist."""
    from app.models.database import get_db, User
    db = next(get_db())
    test_user = db.query(User).filter(User.username == "test").first()
    if not test_user:
        test_user = User(
            username="Test",
            name="Test User",
            email="test@contentguard.ai",
            password=get_password_hash("test@123654123"),
            is_admin=False,
            is_active=True,
            is_verified=True
        )
        db.add(test_user)
        db.commit()
        print(f"✅ Test user created: username={username}, password={password}")
    else:
        print("ℹ️ Test user already exists")
    db.close()

# def create_Manas_user():
#     """Create a test user with username 'test' and password 'test@123' if it doesn't exist."""
#     from app.models.database import get_db, User
#     db = next(get_db())
#     test_user = db.query(User).filter(User.username == "Manas").first()
#     if not test_user:
#         test_user = User(
#             username="Manas",
#             name="Manas Mani",
#             email="manasmani@contentguard.ai",
#             password=get_password_hash("Manas@Rec147"),
#             is_admin=False,
#             is_active=True,
#             is_verified=True
#         )
#         db.add(test_user)
#         db.commit()
#         print(f"✅ Test user created: username={username}, password={password}")

#     else:
#         print("ℹ️ Test user already exists Manas")
#     db.close()


def create_Manas_user():
    """Create a test user with username 'test' and password 'test@123' if it doesn't exist."""
    from app.models.database import get_db, User
    db = next(get_db())
    test_user = db.query(User).filter(User.username == "Manas").first()
    if not test_user:
        test_user = User(
            username="Manas",
            name="Manas Mani",
            email="manasmani@contentguard.ai",
            password=get_password_hash("Manas@Rec147"),
            is_admin=False,
            is_active=True,
            is_verified=True
        )
        db.add(test_user)
        db.commit()
        print(f"✅ Test user created: username={username}, password={password}")
    else:
        print("ℹ️ Test user already exists Manas")
    db.close()


def create_Suraj_user():
    """Create a test user with username 'test' and password 'test@123' if it doesn't exist."""
    from app.models.database import get_db, User
    db = next(get_db())
    test_user = db.query(User).filter(User.username == "Suraj").first()
    if not test_user:
        test_user = User(
            username="Suraj",
            name="Suraj Kumar",
            email="surajkumar@contentguard.ai",
            password=get_password_hash("Suraj@Rec258"),
            is_admin=False,
            is_active=True,
            is_verified=True
        )
        db.add(test_user)
        db.commit()
        print(f"✅ Test user created: username={username}, password={password}")
    else:
        print("ℹ️ Test user already exists Suraj")
    db.close()

from app.models.database import Notification, User

def notify_admins(db: Session, message: str):
    """Send a notification to all admin users."""
    admins = db.query(User).filter(User.is_admin == True).all()
    for admin in admins:
        notif = Notification(
            user_id=admin.id,
            message=message,
            is_read=False
        )
        db.add(notif)
    db.commit()
    