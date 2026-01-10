from datasets import load_dataset
# 1. Load a sample of the LMSYS-Chat-1M dataset (1 million real AI chats)
# We use 'streaming=True' to avoid downloading 100GB at once.
ds = load_dataset("lmsys/lmsys-chat-1m", split="train", streaming=True)

print("Fetching real user queries for daily life prompts...")
for i, example in enumerate(ds):
    # Extract the first message of the conversation
    user_query = example['conversation'][0]['content']
    print(f"{i+1}. User Asked: {user_query}")
    
    if i >= 10: break # Just look at the first 10 for now