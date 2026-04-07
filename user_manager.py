# user_manager.py
import json
import hashlib
import secrets
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# User data file location
USER_DATA_FILE = Path(__file__).parent / "data" / "users.json"
ADMIN_EMAILS = ["dinesh.gujjar@madisonindia.com"]

class UserManager:
    """Manages user authentication and permissions"""
    
    def __init__(self):
        self.user_file = USER_DATA_FILE
        self.users = self._load_users()
    
    def _load_users(self) -> Dict:
        """Load users from JSON file"""
        if self.user_file.exists():
            try:
                with open(self.user_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading users: {e}")
                return {}
        return {}
    
    def _save_users(self):
        """Save users to JSON file"""
        try:
            self.user_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.user_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving users: {e}")
    
    def _hash_password(self, password: str) -> str:
        """Hash password with salt"""
        salt = secrets.token_hex(16)
        hash_val = hashlib.sha256((password + salt).encode()).hexdigest()
        return f"{hash_val}:{salt}"
    
    def _verify_password(self, stored_hash: str, password: str) -> bool:
        """Verify password against stored hash"""
        if not stored_hash:
            return False
        
        try:
            if ":" in stored_hash:
                hash_val, salt = stored_hash.split(":")
                new_hash = hashlib.sha256((password + salt).encode()).hexdigest()
                return new_hash == hash_val
            else:
                return stored_hash == hashlib.sha256(password.encode()).hexdigest()
        except Exception:
            return False
    
    def create_user(self, email: str, name: str, password: str, 
                    role: str = "viewer") -> bool:
        """Create a new user"""
        email = email.lower().strip()
        
        if email in self.users:
            return False
        
        self.users[email] = {
            "name": name.strip(),
            "email": email,
            "password_hash": self._hash_password(password),
            "role": role,
            "created_at": datetime.now().isoformat(),
            "last_login": None,
            "is_active": True
        }
        self._save_users()
        return True
    
    def authenticate(self, email: str, password: str) -> Optional[Dict]:
        """Authenticate user and return user data if successful"""
        email = email.lower().strip()
        user = self.users.get(email)
        
        if not user:
            return None
        
        if not user.get("is_active", True):
            return None
        
        if self._verify_password(user["password_hash"], password):
            user["last_login"] = datetime.now().isoformat()
            self._save_users()
            
            return {
                "email": email,
                "name": user["name"],
                "role": user["role"]
            }
        
        return None
    
    def get_user(self, email: str) -> Optional[Dict]:
        """Get user data"""
        email = email.lower().strip()
        return self.users.get(email)
    
    def is_admin(self, email: str) -> bool:
        """Check if user is admin"""
        email = email.lower().strip()
        user = self.users.get(email)
        if not user:
            return False
        return user.get("role") == "admin" or email in ADMIN_EMAILS
    
    def list_users(self) -> List[Dict]:
        """List all users"""
        users_list = []
        for email, user in self.users.items():
            users_list.append({
                "email": email,
                "name": user.get("name", ""),
                "role": user.get("role", "viewer"),
                "created_at": user.get("created_at", ""),
                "last_login": user.get("last_login", ""),
                "is_active": user.get("is_active", True)
            })
        return users_list
    
    def toggle_user_status(self, email: str) -> bool:
        """Activate/deactivate a user"""
        email = email.lower().strip()
        if email in self.users:
            current_status = self.users[email].get("is_active", True)
            self.users[email]["is_active"] = not current_status
            self._save_users()
            return True
        return False
    
    def delete_user(self, email: str) -> bool:
        """Delete a user"""
        email = email.lower().strip()
        if email in self.users:
            del self.users[email]
            self._save_users()
            return True
        return False

# Global instance
_user_manager = None

def get_user_manager():
    """Get singleton instance of UserManager"""
    global _user_manager
    if _user_manager is None:
        _user_manager = UserManager()
    return _user_manager
