# setup_admin.py
import sys
import getpass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from user_manager import get_user_manager

def setup_admin():
    user_manager = get_user_manager()
    
    print("\n" + "="*50)
    print("MADISON ADS DASHBOARD - ADMIN SETUP")
    print("="*50 + "\n")
    
    email = input("Admin Email: ").strip().lower()
    name = input("Admin Name: ").strip()
    password = getpass.getpass("Admin Password: ")
    confirm = getpass.getpass("Confirm Password: ")
    
    if password != confirm:
        print("\n❌ Passwords do not match!")
        return False
    
    success = user_manager.create_user(email, name, password, role="admin")
    
    if success:
        print(f"\n✅ Admin user '{email}' created successfully!")
        print("\nYou can now login to the dashboard with these credentials.")
    else:
        print(f"\n❌ Failed to create user.")
    
    return success

if __name__ == "__main__":
    setup_admin()
