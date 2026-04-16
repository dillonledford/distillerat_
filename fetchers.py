import requests
import feedparser
from datetime import datetime, timedelta, timezone

def fetch_feed(url, days=1):
    feed = feedparser.parse(url)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    items = []
    for entry in feed.entries:
        parsed = getattr(entry, 'published_parsed', None) or getattr(entry, 'updated_parsed', None)
        if not parsed:
            continue
        published = datetime(*parsed[:6], tzinfo=timezone.utc)
        if published >= cutoff:
            items.append(f"Title: {entry.title}\nSummary: {entry.get('summary', '')}")
    return items

def fetch_drive_folder(folder_id, token, days=7):
    headers = {"Authorization": f"Bearer {token}"}
    
    # Calculate time cutoff
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_str = cutoff.isoformat()
    
    # Find modified files in folder
    query = f"'{folder_id}' in parents and modifiedTime > '{cutoff_str}'"
    drive_resp = requests.get(
        "https://www.googleapis.com/drive/v3/files",
        headers=headers,
        params={
            "q": query,
            "fields": "files(id, name, mimeType, modifiedTime)",
            "orderBy": "modifiedTime desc"
        }
    )
    files = drive_resp.json().get('files', [])
    
    summary = f"Google Drive Folder - {len(files)} files modified in timeframe:\n\n"
    
    for file in files:
        summary += f"File: {file['name']} (modified: {file['modifiedTime']})\n"
        
        # If it's a Google Doc, read the content
        if file['mimeType'] == 'application/vnd.google-apps.document':
            doc_resp = requests.get(
                f"https://docs.googleapis.com/v1/documents/{file['id']}",
                headers=headers
            )
            doc_data = doc_resp.json()
            
            # Extract text from doc
            text = ""
            for element in doc_data.get('body', {}).get('content', []):
                for para_element in element.get('paragraph', {}).get('elements', []):
                    text += para_element.get('textRun', {}).get('content', '')
            
            summary += f"Content:\n{text[:2000]}\n\n"  # limit to 2000 chars per doc
        else:
            summary += f"Type: {file['mimeType']}\n\n"
    
    return summary
