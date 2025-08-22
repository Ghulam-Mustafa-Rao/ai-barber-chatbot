💈 AI Barber Shop Chatbot
1. Overview

This project is an AI-powered chatbot designed for barbershops. Customers can book, view, or cancel appointments in natural language. The chatbot uses Gradio for the interface and Firebase Firestore for backend storage.

✨ Features

🗣️ Chat-based booking, viewing, and cancellation

⏰ Real-time barber availability (working hours, breaks)

💇 Services & pricing info available directly in chat

🚫 Blocks invalid times (past, closed hours, overlaps)

🌐 Works on mobile & web (Gradio share link)

☁️ Firebase Firestore backend

🤖 Hugging Face models for intent detection + natural replies

2. Why This Project?

Unlike form-based tools (Calendly, etc.), this chatbot feels like a human assistant. It improves the booking experience for small businesses by:

✅ Using a conversational interface

✅ Handling real-time availability & schedule changes

✅ Being mobile-friendly via Gradio

✅ Offering optional admin control (React panel)

3. Project Structure
AI-Chatbot/
│── app/
│   ├── app.py                # Main chatbot with Gradio UI
│   ├── requirements.txt      # For Hugging Face model upload
│   └── Firebase/
│       └── firebase_utils.py # Firebase helper functions
│
│── models/
│   └── intent_model/         # Trained intent classification model
│
│── training/
│   ├── TrainModel.py         # Train intent model
│   ├── UploadModel.py        # Upload trained model to Hugging Face Hub
│   └── Dataset/
│       ├── intent_train.json
│       ├── intent_val.json
│       └── generate_intent_dataset.py  # Script to generate training dataset
│
│── requirements-dev.txt      # Dev dependencies (install from here)
│── README.md
│── .gitignore
│── .env

4. Requirements

Python: 3.10.11

Firebase Firestore project set up

Hugging Face account & token

5. Installation

Clone repo:

git clone https://github.com/your-username/ai-barber-chatbot.git
cd ai-barber-chatbot


Create virtual environment:

python3 -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows


Install dependencies:

pip install -r requirements-dev.txt

6. Environment Variables

Create a .env in project root:

# Firebase credentials (paste full JSON as single line)
FIREBASE_CREDENTIALS={"type":"service_account","project_id":"...","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...etc"}

# Hugging Face API token (for inference in chatbot)
HF_TOKEN=your_hf_inference_token

# Hugging Face login token (for uploading models)
HF_TOKEN_LOGIN=your_hf_login_token

# Model ID for Hugging Face Hub (where trained model will be uploaded)
MODEL_ID=your-username/Barber_Intent_Bot


⚠️ .env is already ignored in .gitignore.

7. Firebase Setup

Firestore collections needed:

barbers → { name, speciality, workingHours, breakTimes }

services → { name, price }

appointments → { userId, barberId, barberName, date, time, duration, status }

8. Running the Chatbot

Start the chatbot:

python app/app.py


This launches Gradio UI → you’ll get a local + shareable web link.

9. Training the Model

To retrain intent classification:

python training/TrainModel.py


Reads training data from training/Dataset/intent_train.json

Saves trained model in models/intent_model/

Generating Training Data

If you want to regenerate or expand the dataset, run:

python training/Dataset/generate_intent_dataset.py


This will automatically generate intent classification samples for training and validation.

10. Uploading the Model to Hugging Face

To push trained model to Hugging Face Hub:

Make sure .env has:

HF_TOKEN_LOGIN=your_hf_login_token
MODEL_ID=your-username/Barber_Intent_Bot


Run:

python training/UploadModel.py


This will:

Authenticate with Hugging Face

Create repo if missing

Upload models/intent_model/ to Hub

11. Workflow Diagram
flowchart TD
    A[User Input in Gradio] --> B[Intent Model (Transformers)]
    B --> C{Intent Type}
    C -->|Booking| D[Firebase Firestore - Appointments]
    C -->|View Services| E[Firebase Firestore - Services]
    C -->|Cancel/View| F[Firebase Firestore - Appointments]
    D --> G[System Response]
    E --> G[System Response]
    F --> G[System Response]
    G --> H[Hugging Face LLM - Natural Reply]
    H --> I[Gradio Chatbot Output]

12. Example Conversations

User: "Book me a haircut with Ali tomorrow evening"
Bot: "✅ Appointment booked with Ali on 2025-08-23 at 17:00."

User: "Show me the services"
Bot: "💇 Our services: Haircut - 500 PKR, Beard Trim - 300 PKR."

13. Roadmap

React-based Admin Panel

WhatsApp / Messenger chatbot integration

Voice interface

Analytics dashboard

14. License

MIT License – free to use and modify.
