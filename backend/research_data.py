import pandas as pd
from datasets import load_dataset

# We use "Abhishekcr448/Hinglish-Everyday-Conversations-1M" 
# It is specifically made for Indian day-to-day life topics.
dataset_name = "Abhishekcr448/Hinglish-Everyday-Conversations-1M"

print(f"Streaming dataset: {dataset_name}...")

# 1. Load the dataset in streaming mode (Safe for your RAM)
ds = load_dataset(dataset_name, split="train", streaming=True)

# 2. Define keywords that define "Everyday India"
indian_keywords = ["biryani", "metro", "upi", "diwali", "recharge", "aadhaar", "auto", "train", "office", "recipe"]

filtered_queries = []

# 3. Iterate through the stream and capture relevant conversations
# Updated Step 3 in your research_data.py
for i, entry in enumerate(ds):
    # The dataset uses 'input' for the user query
    query = entry['input'].lower() 
    
    if any(word in query for word in indian_keywords):
        # Save the actual Hinglish text
        filtered_queries.append(entry['input'])
        
    if len(filtered_queries) >= 20:
        break

# 4. Display for your System Prompt refinement
print("\n--- Top 20 Indian Context Queries Found ---")
for idx, q in enumerate(filtered_queries):
    print(f"{idx+1}. {q}")