import os, base64, uuid, scipy.io.wavfile as wavfile, noisereduce as nr
import pandas as pd
import PyPDF2
import docx
import zipfile
import py7zr  # For .7z support
import pyttsx3 # For Zira/David Voice
from groq import Groq
from dotenv import load_dotenv
from gtts import gTTS
from PIL import Image, ImageEnhance

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

PERSONAS = {
    "Default": "Standard preset style and tone.",
    "Professional": "Polished and precise.",
    "Friendly": "Warm and chatty.",
    "Candid": "Direct and encouraging.",
    "Quirky": "Playful and imaginative.",
    "Efficient": "Concise and plain.",
    "Nerdy": "Exploratory and enthusiastic.",
    "Cynical": "Critical and sarcastic."
}

# --- HELPER: READ CONTENT FROM ANY FILE TYPE ---
def get_file_text(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    try:
        text_extensions = {'.txt', '.py', '.java', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.json', '.cpp', '.c', '.php', '.rb', '.go', '.sh', '.md'}
        if ext in text_extensions or ext == "":
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f"\n--- File: {os.path.basename(file_path)} ---\n{f.read()}\n"
        elif ext == ".pdf":
            text = ""
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() or ""
            return f"\n--- PDF: {os.path.basename(file_path)} ---\n{text}\n"
        elif ext == ".docx":
            doc = docx.Document(file_path)
            text = "\n".join([p.text for p in doc.paragraphs])
            return f"\n--- Word: {os.path.basename(file_path)} ---\n{text}\n"
        elif ext == ".csv":
            df = pd.read_csv(file_path)
            return f"\n--- CSV Data: {os.path.basename(file_path)} ---\n{df.head(20).to_string()}\n"
        elif ext == ".xlsx":
            df = pd.read_excel(file_path)
            return f"\n--- Excel Data: {os.path.basename(file_path)} ---\n{df.head(20).to_string()}\n"
    except Exception as e:
        return f"\n[Error reading {os.path.basename(file_path)}: {str(e)}]\n"
    return ""

# --- MAIN STREAMING FUNCTION ---
def get_synapse_streaming(user_text, lang_code, chat_history, image_path=None, doc_path=None, fast_mode=False, persona="Default", location="Unknown"):
    # 1. AUTO-FALLBACK LIST: If one model is down, it tries the next one
    vision_models = ["llama-3.2-90b-vision-preview", "llama-3.2-11b-vision-preview"]
    text_models = ["llama-3.1-8b-instant"] if fast_mode else ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile"]
    
    models_to_try = vision_models if image_path else text_models
    
    # 2. MAP/LOCATION & PERSONA LOGIC (RESTORED)
    tone_description = PERSONAS.get(persona, PERSONAS["Default"])
    loc_context = f"The user is in {location}, India. " if location != "Unknown" else ""

    # 3. DOCUMENT PROCESSING (RESTORED)
    doc_context = ""
    if doc_path and os.path.exists(doc_path):
        ext = os.path.splitext(doc_path)[1].lower()
        if ext in [".zip", ".7z"]:
            extract_dir = os.path.join(os.path.dirname(doc_path), f"ext_{uuid.uuid4().hex[:6]}")
            os.makedirs(extract_dir, exist_ok=True)
            try:
                if ext == ".zip":
                    with zipfile.ZipFile(doc_path, 'r') as zip_ref:
                        zip_ref.extractall(extract_dir)
                else:
                    with py7zr.SevenZipFile(doc_path, mode='r') as z:
                        z.extractall(path=extract_dir)
                
                doc_context += f"\n[ARCHIVE CONTENTS - {os.path.basename(doc_path)}]:\n"
                for root, dirs, files in os.walk(extract_dir):
                    for file in files:
                        full_p = os.path.join(root, file)
                        doc_context += get_file_text(full_p)
            except Exception as e:
                doc_context = f"\n[Archive Extraction Error: {str(e)}]\n"
        else:
            doc_context = get_file_text(doc_path)

    system_prompt = (
        f"You are Synapse-V, an AI for Everyday India. {loc_context}"
        f"Respond in {'Hindi' if lang_code == 'hi' else 'English'}. "
        f"TONE: {tone_description} "
        "CONTEXT: You understand code files, archives, and Indian nuances. "
        "Analyze any code or document provided. If you see code, explain it or debug it if asked. "
        "Never say 'As an AI model'."
    )
    
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(chat_history)
    
    if len(doc_context) > 20000:
        doc_context = doc_context[:20000] + "\n... [Content Truncated] ..."

    full_user_query = f"{doc_context}\nUSER REQUEST: {user_text}"
    
    if image_path:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode('utf-8')
        content = [
            {"type": "text", "text": full_user_query},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
        ]
        messages.append({"role": "user", "content": content})
    else:
        messages.append({"role": "user", "content": full_user_query})
    
    # 4. AUTO-RETRY LOOP
    completion = None
    for model_id in models_to_try:
        try:
            completion = client.chat.completions.create(model=model_id, messages=messages, stream=True)
            break # Success!
        except Exception as e:
            print(f"Model {model_id} failed. Trying next... Error: {e}")
            continue

    if not completion:
        yield "Error: All models are currently unavailable on Groq. Please try again later."
        return

    for chunk in completion:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content

# --- VOICE UTILITIES (RESTORED) ---
def text_to_speech(text, upload_dir, lang='en', voice="Zira"):
    fn = f"res_{uuid.uuid4().hex[:8]}.mp3"
    full_path = os.path.join(upload_dir, fn)
    
    if voice in ["Zira", "David"]:
        try:
            engine = pyttsx3.init()
            voices = engine.getProperty('voices')
            target_voice = None
            for v in voices:
                if voice.lower() in v.name.lower():
                    target_voice = v.id
                    break
            if not target_voice:
                if voice == "David" and len(voices) > 0: target_voice = voices[0].id
                elif voice == "Zira" and len(voices) > 1: target_voice = voices[1].id

            if target_voice:
                engine.setProperty('voice', target_voice)
            
            engine.setProperty('rate', 180)
            engine.save_to_file(text[:500], full_path)
            engine.runAndWait()
            engine.stop() 
            return fn
        except Exception as e:
            print(f"Local TTS Error: {e}")
    
    try:
        tts = gTTS(text=text[:500], lang=lang)
        tts.save(full_path)
        return fn
    except:
        return None

# --- IMAGE/AUDIO UTILITIES (RESTORED) ---
def reduce_audio_noise(file_path):
    try:
        rate, data = wavfile.read(file_path)
        reduced_noise = nr.reduce_noise(y=data, sr=rate, prop_decrease=0.8)
        wavfile.write(file_path, rate, reduced_noise)
    except: pass

def transcribe_audio(file_path, lang='en'):
    try:
        with open(file_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(file_path, file.read()),
                model="whisper-large-v3-turbo",
                language=lang,
                response_format="text"
            )
        return transcription.strip()
    except: return "Transcription error."

def enhance_low_light(p):
    with Image.open(p) as i:
        i = ImageEnhance.Brightness(i).enhance(1.5)
        i.save(p)

def compress_image(p):
    with Image.open(p) as i:
        i.thumbnail((1024, 1024))
        i.save(p, quality=40)