import os
import requests
from datetime import datetime
import streamlit as st

# Default Supabase Storage configuration
SUPABASE_URL = "https://vistjnuohkunrrgifolw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZpc3RqbnVvaGt1bnJyZ2lmb2x3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQ1NTkyMTcsImV4cCI6MjEwMDEzNTIxN30.nH1n6YfyE8ky3CRZiTqpNqMRl-oI-0OYSzj5CYKa7MI"
BUCKET_NAME = "workflow-files"

# Check secrets for overrides if present
try:
    if hasattr(st, "secrets"):
        for sec_name in ["supabase", "email", "email_workflow"]:
            if sec_name in st.secrets:
                s = st.secrets[sec_name]
                if "SUPABASE_URL" in s: SUPABASE_URL = s["SUPABASE_URL"]
                if "SUPABASE_KEY" in s: SUPABASE_KEY = s["SUPABASE_KEY"]
                if "SUPABASE_ANON_KEY" in s: SUPABASE_KEY = s["SUPABASE_ANON_KEY"]
        if "SUPABASE_URL" in st.secrets: SUPABASE_URL = st.secrets["SUPABASE_URL"]
        if "SUPABASE_KEY" in st.secrets: SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception:
    pass

LOCAL_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads')
os.makedirs(LOCAL_UPLOAD_DIR, exist_ok=True)

class StorageService:
    @staticmethod
    def upload_file(file_bytes: bytes, filename: str, folder: str = "attachments") -> str:
        """
        Uploads file_bytes to Supabase Storage.
        Returns the public URL if uploaded to Supabase, or local path as fallback.
        """
        timestamp_prefix = datetime.now().strftime("%Y%m%d%H%M%S")
        safe_filename = f"{timestamp_prefix}_{filename.replace(' ', '_')}"
        object_path = f"{folder}/{safe_filename}"
        
        if SUPABASE_URL and SUPABASE_KEY:
            try:
                upload_url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/{BUCKET_NAME}/{object_path}"
                headers = {
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "apikey": SUPABASE_KEY,
                    "x-upsert": "true"
                }
                res = requests.post(upload_url, data=file_bytes, headers=headers, timeout=15)
                if res.status_code in [200, 201]:
                    public_url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{BUCKET_NAME}/{object_path}"
                    return public_url
                else:
                    print(f"Supabase storage upload status {res.status_code}: {res.text}")
            except Exception as ex:
                print(f"Error uploading to Supabase Storage: {ex}")

        # Local fallback
        local_path = os.path.join(LOCAL_UPLOAD_DIR, safe_filename)
        with open(local_path, "wb") as f:
            f.write(file_bytes)
        return local_path

    @staticmethod
    def get_file_bytes(file_path_or_url: str) -> bytes:
        """
        Retrieves raw bytes from a public URL or local file path.
        """
        if not file_path_or_url:
            return None

        if file_path_or_url.startswith("http://") or file_path_or_url.startswith("https://"):
            try:
                res = requests.get(file_path_or_url, timeout=15)
                if res.status_code == 200:
                    return res.content
            except Exception as ex:
                print(f"Error downloading file from URL '{file_path_or_url}': {ex}")
            return None
        else:
            if os.path.exists(file_path_or_url):
                try:
                    with open(file_path_or_url, "rb") as f:
                        return f.read()
                except Exception as ex:
                    print(f"Error reading local file '{file_path_or_url}': {ex}")
                    return None
            else:
                alt_path = os.path.join(LOCAL_UPLOAD_DIR, os.path.basename(file_path_or_url))
                if os.path.exists(alt_path):
                    try:
                        with open(alt_path, "rb") as f:
                            return f.read()
                    except Exception:
                        pass
            return None
