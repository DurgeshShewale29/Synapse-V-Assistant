import os
import shutil
import uuid
import json
import uvicorn
import time
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from typing import Optional
from contextlib import asynccontextmanager

# Importing your custom logic modules
from engine import (
    get_synapse_streaming, 
    text_to_speech, 
    transcribe_audio, 
    reduce_audio_noise, 
    compress_image, 
    enhance_low_light
)
from database import (
    create_db_and_tables, 
    save_interaction, 
    update_interaction, 
    get_all_history, 
    delete_all_history, 
    delete_specific_interaction
)

# --- LIFESPAN HANDLER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes database on launch."""
    create_db_and_tables()
    yield

app = FastAPI(title="Synapse-V Backend", lifespan=lifespan)

# Ensure upload directory exists
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- CATEGORIZED FILE EXPLORER ---
@app.get("/list_files")
async def list_files():
    """Lists files grouped by category for the sidebar explorer."""
    if not os.path.exists(UPLOAD_DIR): 
        return {"images": [], "documents": [], "audio": []}
    
    categories = {"images": [], "documents": [], "audio": []}
    
    # Extension mappings
    ext_map = {
        'images': {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'},
        'audio': {'.wav', '.mp3', '.m4a', '.flac', '.ogg'},
        'documents': {'.pdf', '.docx', '.csv', '.xlsx', '.txt', '.py', '.zip', '.7z', '.java', '.js'}
    }

    for f in os.listdir(UPLOAD_DIR):
        p = os.path.join(UPLOAD_DIR, f)
        if os.path.isfile(p):
            ext = os.path.splitext(f)[1].lower()
            file_info = {
                "name": f,
                "size": f"{os.path.getsize(p) / 1024:.1f} KB",
                "date": time.strftime('%d %b, %H:%M', time.localtime(os.path.getmtime(p)))
            }
            
            if ext in ext_map['images']:
                categories['images'].append(file_info)
            elif ext in ext_map['audio']:
                categories['audio'].append(file_info)
            else:
                categories['documents'].append(file_info)
    
    return categories

@app.delete("/delete_file/{filename}")
async def delete_file(filename: str):
    """Deletes a specific file from the server."""
    p = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(p):
        os.remove(p)
        return {"status": "deleted"}
    return {"status": "error", "message": "File not found"}

# --- STREAM PROCESS ---
@app.post("/stream_process")
async def stream_process(
    text: str = Form(...), 
    lang: str = Form("en"), 
    history: str = Form("[]"), 
    fast: bool = Form(False),
    persona: str = Form("Default"), 
    location: str = Form("Unknown"),
    image: Optional[UploadFile] = File(None),
    document: Optional[UploadFile] = File(None),
    low_light: bool = Form(False)
):
    img_path = None
    doc_path = None

    if image:
        # Robust naming for uploaded vs captured images
        orig_ext = os.path.splitext(image.filename)[1] if image.filename else ".jpg"
        img_path = os.path.join(UPLOAD_DIR, f"img_{uuid.uuid4().hex}{orig_ext}")
        with open(img_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        compress_image(img_path)
        if low_light: enhance_low_light(img_path)

    if document:
        doc_path = os.path.join(UPLOAD_DIR, f"doc_{uuid.uuid4().hex}_{document.filename}")
        with open(doc_path, "wb") as buffer:
            shutil.copyfileobj(document.file, buffer)

    return StreamingResponse(
        get_synapse_streaming(
            user_text=text, 
            lang_code=lang, 
            chat_history=json.loads(history), 
            image_path=img_path, 
            doc_path=doc_path, 
            fast_mode=fast, 
            persona=persona,
            location=location 
        ), 
        media_type="text/plain"
    )

@app.post("/process_voice")
async def process_voice(
    audio: UploadFile = File(...), 
    lang: str = Form("en"), 
    noise: bool = Form(False)
):
    path = os.path.join(UPLOAD_DIR, f"v_{uuid.uuid4().hex}.wav")
    with open(path, "wb") as buffer:
        shutil.copyfileobj(audio.file, buffer)
    if noise:
        reduce_audio_noise(path)
    transcription = transcribe_audio(path, lang)
    return {"text": transcription}

@app.post("/get_audio")
async def get_audio_api(
    text: str = Form(...), 
    lang: str = Form("en"),
    voice: str = Form("Zira") 
):
    fn = text_to_speech(text, UPLOAD_DIR, lang, voice=voice)
    if fn:
        return {"audio_url": f"{fn}"}
    return {"error": "TTS Failed"}

@app.get("/listen/{filename}")
async def listen(filename: str):
    return FileResponse(os.path.join(UPLOAD_DIR, filename))

@app.get("/history")
async def fetch_history():
    return get_all_history()

@app.delete("/clear_history")
async def clear_all_history():
    delete_all_history()
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)