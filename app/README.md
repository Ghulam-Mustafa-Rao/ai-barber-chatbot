---
title: AI Barber Chat Bot
emoji: 💈
colorFrom: indigo
colorTo: pink
sdk: gradio
sdk_version: 5.42.0
app_file: app.py
pinned: false
license: apache-2.0
---

# 💈 AI Barber Chat Bot

An AI-powered chatbot for a barber shop, built with:
- **LoRA fine-tuned Flan-T5** for intent recognition
- **Firebase Firestore** for appointment storage
- **Gradio** for the chat UI

## 🚀 Features
- Book, cancel, and view appointments
- Browse services and barbers
- Simple login via email

## 🛠️ Usage
1. Enter your email to log in
2. Chat naturally (e.g., *“Book me a haircut tomorrow at 3 PM”*)
3. The bot manages appointments in Firestore

## 🔑 Configuration
- Add your Firebase service account key in Hugging Face **Secrets**  
  (Settings → Secrets → `FIREBASE_CREDENTIALS`)

## 📜 License
Apache-2.0
