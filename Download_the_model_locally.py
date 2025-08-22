from transformers import AutoTokenizer, AutoModelForCausalLM
from huggingface_hub import login
from dotenv import load_dotenv
import os
import torch

# Load .env file
load_dotenv()
token = os.getenv("HF_TOKEN_LOGIN")

if not token:
    raise ValueError("HF_TOKEN_LOGIN not found. Please set it in your .env file.")

# Login to Hugging Face
login(token)

# Local path to save the model
MODEL_PATH = "models/local_text_gen"

# Model to download
model_name = "gpt2-medium"  # CPU-compatible model

# Device setup
DEVICE = "cpu"

# Download tokenizer and model
print("Downloading tokenizer and model...")
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name).to(DEVICE)
model.eval()

# Save locally
tokenizer.save_pretrained(MODEL_PATH)
model.save_pretrained(MODEL_PATH)
print(f"✅ Model downloaded and saved locally to {MODEL_PATH}")
