#!/usr/bin/env python3
"""
MySQL Database Initialization Script for ContentGuard AI
Run this script to create/initialize all required tables in contentguard_auth database
"""

import mysql.connector
from mysql.connector import Error
import bcrypt
from datetime import datetime

# MySQL Configuration
MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "ramramroot",  # Change this to your MySQL root password
    "database": "contentguard_auth",
}

def get_password_hash(password: str) -> str:
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def initialize_mysql_database():
    """Complete MySQL database initialization"""
    try:
        # First connect without database to ensure it exists
        temp_config = MYSQL_CONFIG.copy()
        temp_config.pop("database")
        
        print("📡 Connecting to MySQL server...")
        conn = mysql.connector.connect(**temp_config)
        cursor = conn.cursor()
        
        # Create database if it doesn't exist
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_CONFIG['database']} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        print(f"✅ Database '{MYSQL_CONFIG['database']}' ensured")
        
        cursor.close()
        conn.close()
        
        # Now connect to the specific database
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()
        
        print("📦 Creating/updating tables...")
        
        # ============================================
        # 1. Create users table with all columns
        # ============================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE,
                password VARCHAR(255) NOT NULL,
                name VARCHAR(255),
                
                -- User settings and preferences
                is_admin BOOLEAN DEFAULT FALSE,
                is_active BOOLEAN DEFAULT TRUE,
                is_verified BOOLEAN DEFAULT FALSE,
                theme_preference VARCHAR(50) DEFAULT 'modern',
                
                -- User metadata
                profile_picture VARCHAR(500),
                bio TEXT,
                department VARCHAR(255),
                designation VARCHAR(255),
                
                -- Permissions and roles
                roles JSON DEFAULT ('[]'),
                permissions JSON DEFAULT ('[]'),
                
                -- Tracked comments and activity
                comment_ids TEXT DEFAULT '[]',
                reviewed_comments JSON DEFAULT ('[]'),
                extracted_jobs JSON DEFAULT ('[]'),
                
                -- Account statistics
                total_logins INT DEFAULT 0,
                last_login_ip VARCHAR(50),
                last_login_user_agent TEXT,
                
                -- Timestamps
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                last_login TIMESTAMP NULL,
                last_activity TIMESTAMP NULL,
                password_changed_at TIMESTAMP NULL,
                
                -- Account recovery
                reset_password_token VARCHAR(255),
                reset_password_expires TIMESTAMP NULL,
                email_verification_token VARCHAR(255),
                email_verified_at TIMESTAMP NULL,
                
                -- Two factor authentication
                two_factor_enabled BOOLEAN DEFAULT FALSE,
                two_factor_secret VARCHAR(255),
                backup_codes JSON DEFAULT ('[]'),
                
                -- API access
                api_key VARCHAR(255) UNIQUE,
                api_key_created_at TIMESTAMP NULL,
                api_key_expires TIMESTAMP NULL,
                
                INDEX idx_username (username),
                INDEX idx_email (email),
                INDEX idx_api_key (api_key)
                
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)
        print("✅ Users table created/verified")
        
        # ============================================
        # 2. Create user_comments table for tracking
        # ============================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_comments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) NOT NULL,
                comment_id VARCHAR(255) NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_user_comment (username, comment_id),
                INDEX idx_username (username),
                INDEX idx_comment_id (comment_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)
        print("✅ User comments table created/verified")
        
        # ============================================
        # 3. Create extraction_patterns table
        # ============================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS extraction_patterns (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                pattern_format VARCHAR(500) NOT NULL,
                regex_pattern VARCHAR(500) NOT NULL,
                description TEXT,
                
                -- Pattern components
                tag_placeholder VARCHAR(50) DEFAULT 'tag',
                comment_placeholder VARCHAR(50) DEFAULT 'comment',
                delimiter VARCHAR(50),
                requires_tag BOOLEAN DEFAULT TRUE,
                
                -- Usage statistics
                is_active BOOLEAN DEFAULT FALSE,
                usage_count INT DEFAULT 0,
                last_used TIMESTAMP NULL,
                success_rate FLOAT DEFAULT 0.0,
                
                -- Metadata
                created_by VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                
                INDEX idx_active (is_active)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)
        print("✅ Extraction patterns table created/verified")
        
        # ============================================
        # 4. Create default admin user if not exists
        # ============================================
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
        admin_exists = cursor.fetchone()[0] > 0
        
        if not admin_exists:
            admin_password = get_password_hash("Admin@123")
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute("""
                INSERT INTO users (
                    username, email, password, name, is_admin, is_active, is_verified,
                    theme_preference, total_logins, created_at, updated_at
                ) VALUES (
                    'admin', 'admin@contentguard.ai', %s, 'System Administrator',
                    TRUE, TRUE, TRUE, 'modern', 0, %s, %s
                )
            """, (admin_password, now, now))
            print("✅ Default admin user created (username: admin, password: Admin@123)")
        else:
            print("✅ Admin user already exists")
        
        # ============================================
        # 5. Create default extraction patterns
        # ============================================
        cursor.execute("SELECT COUNT(*) FROM extraction_patterns")
        patterns_count = cursor.fetchone()[0]
        
        if patterns_count == 0:
            default_patterns = [
                ("Tag with Curly Braces", "[tag]{comment}", r'\[(.*?)\]\s*\{(.*?)\}', 
                 "Extracts [tag]{comment} format", "admin", True),
                ("Tag with Colon", "[tag]: comment", r'\[(.*?)\]:\s*(.*)', 
                 "Extracts [tag]: comment format", "admin", False),
                ("Simple Tag", "{tag} comment", r'\{(.*?)\}\s*(.*)', 
                 "Extracts {tag} comment format", "admin", False),
                ("HTML Style", "<tag>comment", r'<(.*?)>(.*)', 
                 "Extracts <tag>comment format", "admin", False)
            ]
            
            for pattern in default_patterns:
                cursor.execute("""
                    INSERT INTO extraction_patterns 
                    (name, pattern_format, regex_pattern, description, created_by, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, pattern)
            print("✅ Default extraction patterns created")
        else:
            print("✅ Extraction patterns already exist")
        
        # Commit all changes
        conn.commit()
        print("\n🎉 MySQL database initialized successfully!")
        print("📊 Tables created/verified:")
        print("   - users")
        print("   - user_comments")
        print("   - extraction_patterns")
        
        # Show some statistics
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"\n👤 Total users in database: {user_count}")
        
        if user_count > 0:
            cursor.execute("SELECT username, is_admin, created_at FROM users ORDER BY created_at DESC LIMIT 5")
            print("\n📋 Recent users:")
            for user in cursor.fetchall():
                admin_flag = " (Admin)" if user[1] else ""
                print(f"   - {user[0]}{admin_flag} (created: {user[2]})")
        
        cursor.close()
        conn.close()
        
    except Error as e:
        print(f"❌ MySQL Error: {e}")
        return False
    
    return True

def verify_database():
    """Verify all tables and columns exist"""
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()
        
        print("\n🔍 Verifying database structure...")
        
        # Check users table columns
        cursor.execute("DESCRIBE users")
        user_columns = cursor.fetchall()
        print(f"\n📋 Users table columns ({len(user_columns)}):")
        for col in user_columns[:10]:  # Show first 10 columns
            print(f"   - {col[0]}: {col[1]}")
        if len(user_columns) > 10:
            print(f"   ... and {len(user_columns) - 10} more columns")
        
        # Check indexes
        cursor.execute("SHOW INDEX FROM users")
        indexes = cursor.fetchall()
        print(f"\n📌 Users table indexes: {len(indexes)}")
        
        # Check table status
        cursor.execute("""
            SELECT table_name, table_rows, engine 
            FROM information_schema.tables 
            WHERE table_schema = 'contentguard_auth'
        """)
        tables = cursor.fetchall()
        print("\n📊 Table statistics:")
        for table in tables:
            print(f"   - {table[0]}: ~{table[1]} rows ({table[2]})")
        
        cursor.close()
        conn.close()
        
        print("\n✅ Database verification complete!")
        return True
        
    except Error as e:
        print(f"❌ Verification error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 ContentGuard AI - MySQL Database Initialization")
    print("=" * 60)
    
    # Initialize database
    if initialize_mysql_database():
        print("\n" + "=" * 60)
        # Verify database
        verify_database()
        print("\n" + "=" * 60)
        print("✨ You can now start your application with: python run.py")
        print("=" * 60)
    else:
        print("\n❌ Database initialization failed. Please check the errors above.")