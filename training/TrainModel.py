import json
from datasets import Dataset, DatasetDict
from transformers import AutoTokenizer, AutoModelForSequenceClassification, TrainingArguments, Trainer
import evaluate
import numpy as np
import os
from huggingface_hub import login
from dotenv import load_dotenv

# Load .env file (make sure .env is in project root)
token = os.getenv("HF_TOKEN_LOGIN")

if not token:
    # Try loading again (or fallback)
    load_dotenv()
    token = os.getenv("HF_TOKEN_LOGIN")

if not token:
    raise ValueError("HF_TOKEN_LOGIN not found. Please set it in your .env file.")

# Login to HuggingFace
login(token)

# ------------------ CONFIG ------------------
MODEL_NAME = "Falconsai/intent_classification"
LABELS = ["cancel_appointment", "view_appointments", "list_barbers",
          "list_services", "small_talk", "book_appointment"]

label2id = {label: i for i, label in enumerate(LABELS)}
id2label = {i: label for label, i in label2id.items()}

# ------------------ LOAD DATA ------------------
def load_json(path):
    with open(path, "r") as f:
        data = json.load(f)
    texts = [item["text"] for item in data]
    labels = [label2id[item["intent"]] for item in data]
    return {"text": texts, "label": labels}

train_data = load_json("Dataset/intent_train.json")
val_data = load_json("Dataset/intent_val.json")

dataset = DatasetDict({
    "train": Dataset.from_dict(train_data),
    "validation": Dataset.from_dict(val_data)
})

# ------------------ TOKENIZER ------------------
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

def preprocess(batch):
    return tokenizer(batch["text"], truncation=True, padding="max_length", max_length=64)

tokenized_dataset = dataset.map(preprocess, batched=True)

# ------------------ MODEL ------------------
model = AutoModelForSequenceClassification.from_pretrained(
    MODEL_NAME,
    num_labels=len(LABELS),
    id2label=id2label,
    label2id=label2id,
    ignore_mismatched_sizes=True   # 👈 important fix
)

# ------------------ TRAINER ------------------
accuracy = evaluate.load("accuracy")
f1 = evaluate.load("f1")

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy.compute(predictions=preds, references=labels)["accuracy"],
        "f1": f1.compute(predictions=preds, references=labels, average="weighted")["f1"]
    }

training_args = TrainingArguments(
    output_dir="models/intent_model",
    eval_strategy="epoch",   # 👈 correct name
    save_strategy="epoch",
    learning_rate=2e-5,
    per_device_train_batch_size=8,
    per_device_eval_batch_size=8,
    num_train_epochs=5,
    weight_decay=0.01,
    warmup_steps=200,           # learning rate warmup
    load_best_model_at_end=True,
    logging_dir="./logs",
     report_to="none",   # 👈 disable wandb
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset["train"],
    eval_dataset=tokenized_dataset["validation"],
    tokenizer=tokenizer,
    compute_metrics=compute_metrics,
)

# ------------------ TRAIN ------------------
trainer.train()

# ------------------ SAVE ------------------
trainer.save_model("./intent_model")
tokenizer.save_pretrained("./intent_model")
