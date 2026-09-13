# Cloud Deployment & Backup Guide - School Room Booking System

This guide outlines how to deploy your Python OOP School Room Booking System to free/low-cost cloud web platforms and configure automated cloud database backups.

---

## 1. Free Cloud Web Hosting Options

### Option A: Render.com (Recommended - 1-Click Deployment)
1. Push your code to a private or public repository on **GitHub**.
2. Log in to [Render.com](https://render.com) and click **New +** -> **Web Service**.
3. Connect your GitHub repository.
4. Render will auto-detect `render.yaml` or set:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
5. Under **Disks**, add a 1GB Persistent Disk mounted at `/app/data` to persist your SQLite database file across redeployments.

---

### Option B: PythonAnywhere (Simple Python Hosting)
1. Create a free account on [PythonAnywhere.com](https://www.pythonanywhere.com).
2. Open a bash console and clone your repo:
   ```bash
   git clone https://github.com/YOUR_USERNAME/school-room-booking.git
   cd school-room-booking
   pip install -r requirements.txt
   ```
3. In the **Web** tab, set:
   - **Source Code Path:** `/home/yourusername/school-room-booking`
   - **WSGI Configuration:** Set entry point to `from app import app as application`.

---

## 2. Cloud Database Backups (`backup_cloud.py`)

Run the cloud backup script at any time to create a timestamped snapshot of your SQLite database:

```bash
# Create a local & S3 cloud backup snapshot
python backup_cloud.py backup
```

### AWS S3 / Cloudflare R2 Integration (Optional)
Set the environment variable `S3_BACKUP_BUCKET`:
```bash
export S3_BACKUP_BUCKET="my-school-booking-backups"
python backup_cloud.py backup
```

---

## 3. GitHub Cloud Repository Setup

Run the following commands to initialize Git and push to your GitHub cloud account:

```bash
git init
git add .
git commit -m "Complete Python OOP School Room Booking application with Cloud Configs"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/school-room-booking.git
git push -u origin main
```
