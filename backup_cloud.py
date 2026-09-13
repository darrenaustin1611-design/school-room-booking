import os
import shutil
import sys
from datetime import datetime
from config import Config

BACKUP_DIR = os.path.join(Config.BASE_DIR, 'cloud_backups')

def create_cloud_backup():
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
        
    db_path = Config.DATABASE_PATH
    if not os.path.exists(db_path):
        print(f"[-] Database file not found at {db_path}. Run the application first.")
        return False
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"school_booking_backup_{timestamp}.db"
    backup_filepath = os.path.join(BACKUP_DIR, backup_filename)
    
    # Safely copy SQLite DB file
    shutil.copy2(db_path, backup_filepath)
    print(f"[+] Local Cloud Backup Created: {backup_filepath}")
    
    # Optional S3 Upload if credentials exist
    s3_bucket = os.environ.get('S3_BACKUP_BUCKET')
    if s3_bucket:
        try:
            import boto3
            s3 = boto3.client('s3')
            s3.upload_file(backup_filepath, s3_bucket, f"backups/{backup_filename}")
            print(f"[+] Successfully uploaded to AWS S3 Bucket: s3://{s3_bucket}/backups/{backup_filename}")
        except Exception as e:
            print(f"[!] S3 Upload skipped or failed: {e}")
            
    return backup_filepath

def restore_backup(backup_file):
    if not os.path.exists(backup_file):
        print(f"[-] Backup file not found: {backup_file}")
        return False
        
    db_path = Config.DATABASE_PATH
    shutil.copy2(backup_file, db_path)
    print(f"[+] Database successfully restored from: {backup_file}")
    return True

if __name__ == '__main__':
    args = sys.argv[1:]
    if not args or args[0] == 'backup':
        create_cloud_backup()
    elif args[0] == 'restore' and len(args) > 1:
        restore_backup(args[1])
    else:
        print("Usage: python backup_cloud.py [backup|restore <backup_filepath>]")
