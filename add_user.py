# add_user.py
import sys
import getpass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from user_manager import get_user_manager

def add_user():
    user_manager = get_user_manager()
    
    print("\n" + "="*50)
    print("ADD NEW USER")
    print("="*50 + "\n")
    
    email = input("User Email: ").strip().lower()
    name = input("Full Name: ").strip()
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm Password: ")
    
    if password != confirm:
        print("❌ Passwords do not match!")
        return
    
    print("\nRole options:")
    print("1. Admin (sees ALL accounts)")
    print("2. Viewer (sees ONLY accounts they have access to)")
    role_choice = input("Choose role (1 or 2): ").strip()
    role = "admin" if role_choice == "1" else "viewer"
    
    success = user_manager.create_user(email, name, password, role)
    
    if success:
        print(f"\n✅ User '{email}' created successfully!")
        print(f"   Role: {role}")
        print(f"\n📤 Share these details with the user:")
        print(f"   URL: http://192.168.1.42:5000")
        print(f"   Email: {email}")
        print(f"   Password: {password}")
        print(f"\n⚠️  IMPORTANT: The password is shown only ONCE. Save it securely.")
    else:
        print(f"\n❌ Failed to create user (user may already exist)")

if __name__ == "__main__":
    add_user()
