from cryptography.fernet import Fernet, InvalidToken
from app.config import settings
import base64
import hashlib

# Initialize Fernet with key from settings
encryption_key = settings.ENCRYPTION_KEY.encode()
fernet = Fernet(encryption_key)

# def encrypt_content(content: str) -> str:
#     """
#     Encrypt content using Fernet symmetric encryption
#     """
#     if not content:
#         return ""
#     try:
#         encrypted = fernet.encrypt(content.encode())
#         return encrypted.decode()
#     except Exception as e:
#         print(f"Encryption error: {e}")
#         return content  # Fallback to plain text in case of error
def encrypt_content(content: str) -> str:
    """Encrypt content using Fernet symmetric encryption."""
    if not content:
        return ""
    try:
        encrypted = fernet.encrypt(content.encode())
        return encrypted.decode()
    except Exception as e:
        # Log the error and raise, so the caller knows encryption failed.
        print(f"Encryption error: {e}")
        raise ValueError(f"Failed to encrypt content: {e}")

def decrypt_content(encrypted_content: str) -> str:
    """
    Decrypt content using Fernet symmetric encryption
    """
    if not encrypted_content:
        return ""
    try:
        decrypted = fernet.decrypt(encrypted_content.encode())
        return decrypted.decode()
    except (InvalidToken, Exception) as e:
        # If decryption fails, return as is (might be already plain text)
        return encrypted_content

def hash_content(content: str) -> str:
    """
    Create SHA-256 hash of content for duplicate detection
    """
    return hashlib.sha256(content.encode()).hexdigest()

def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key
    """
    key = Fernet.generate_key()
    return key.decode()

def encrypt_file(file_path: str, output_path: str = None) -> str:
    """
    Encrypt an entire file
    """
    if not output_path:
        output_path = file_path + ".encrypted"
    
    with open(file_path, 'rb') as f:
        file_data = f.read()
    
    encrypted_data = fernet.encrypt(file_data)
    
    with open(output_path, 'wb') as f:
        f.write(encrypted_data)
    
    return output_path

def decrypt_file(encrypted_path: str, output_path: str = None) -> str:
    """
    Decrypt an encrypted file
    """
    if not output_path:
        output_path = encrypted_path.replace('.encrypted', '')
    
    with open(encrypted_path, 'rb') as f:
        encrypted_data = f.read()
    
    try:
        decrypted_data = fernet.decrypt(encrypted_data)
    except InvalidToken:
        raise ValueError("Invalid encryption key or corrupted file")
    
    with open(output_path, 'wb') as f:
        f.write(decrypted_data)
    
    return output_path