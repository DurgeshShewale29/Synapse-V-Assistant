import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# This will list every model your API key can actually see
models = client.models.list()
for model in models.data:
    if "vision" in model.id.lower():
        print(f"FOUND VISION MODEL: {model.id}")