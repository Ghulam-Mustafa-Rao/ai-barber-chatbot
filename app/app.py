# app.py
import json
import torch
import gradio as gr
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from peft import AutoPeftModelForSeq2SeqLM
import re
from datetime import datetime, timedelta
from huggingface_hub import InferenceClient
import os
from dotenv import load_dotenv

# Firebase utils
try:
    from Firebase import firebase_utils as fu
except ImportError:
    import firebase_utils as fu

# ---------------- CONFIG ----------------


MODEL_PATH = "GMR01231/Barber_Intent_Bot"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

print("Loading model...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH).to(DEVICE)
model.eval()
print("✅ Model ready")


# Labels (must match training order)
id2label = {
    0: "cancel_appointment",
    1: "view_appointments",
    2: "list_barbers",
    3: "list_services",
    4: "small_talk",
    5: "book_appointment"
}

# ---------------- SESSION STATE ----------------
sessions = {}
def get_session(session_id):
    if session_id not in sessions:
        sessions[session_id] = {"intent": None, "barber": None, "date": None, "time": None}
    return sessions[session_id]

DATE_VERBAL = ["today", "tomorrow"]
DOWS = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
SLOT_MAPPING = {
    "morning": "11:00",
    "afternoon": "14:00",
    "evening": "17:00",
    "as soon as possible": None  # leave None if ASAP
}

def detect_date_time(message: str):
    message = message.lower()
    chosen_date, chosen_time = None, None

    # --- DATE HANDLING ---
    if "today" in message:
        chosen_date = datetime.now().strftime("%Y-%m-%d")
    elif "tomorrow" in message:
        chosen_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        for i, dow in enumerate(DOWS):
            if dow in message:
                today_idx = datetime.now().weekday()
                days_ahead = (i - today_idx) % 7
                if days_ahead == 0:  # same day → assume next week
                    days_ahead = 7
                chosen_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
                break

    # --- TIME HANDLING ---
    for slot, mapped_time in SLOT_MAPPING.items():
        if slot in message:
            chosen_time = mapped_time
            break

    if chosen_time is None:
        match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", message)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2) or 0)
            meridian = (match.group(3) or "").lower()
            if meridian == "pm" and hour != 12:
                hour += 12
            elif meridian == "am" and hour == 12:
                hour = 0
            chosen_time = f"{hour:02d}:{minute:02d}"

    return chosen_date, chosen_time

# ---------------- ROUTER ----------------
def route_intent(parsed, message, session_id="default", user_email="demo@example.com"):
    sess = get_session(session_id)
    intent = parsed.get("intent")
    for k in ["barber", "date", "time"]:
        if parsed.get(k):
            sess[k] = parsed[k]
    sess["intent"] = intent

    # -------- BARBERS --------
    if intent == "list_barbers":
        try:
            barbers = fu.get_all_barbers()
            if not barbers:
                return "❌ No barbers found."
            names = ", ".join(b["name"] for b in barbers if "name" in b)
            return f"💈 We have {len(barbers)} barbers: {names}."
        except Exception as e:
            return str(f"⚠️ Couldn't fetch barbers: {e}")

    # -------- SERVICES --------
    elif intent == "list_services":
        try:
            services = fu.get_all_services()
            if not services:
                return "❌ No services found."
            items = [f"{s['name']} - {s.get('price','N/A')} PKR" for s in services]
            return "💇‍♂️ Our services:\n" + "\n".join(items)
        except Exception as e:
            return str(f"⚠️ Couldn't fetch services: {e}")

    # -------- BOOK --------
    elif intent == "book_appointment":
        chosen_barber = sess.get("barber")
        chosen_date = sess.get("date")
        chosen_time = sess.get("time")

        # Fallback: extract date/time from message if missing
        if not chosen_date or chosen_time is None:
            extracted_date, extracted_time = detect_date_time(message)
            if not chosen_date:
                chosen_date = extracted_date
            if chosen_time is None:  # allow None for "as soon as possible"
                chosen_time = extracted_time

        try:
            success, msg = fu.book_appointment(
                user_email,
                barber_name=chosen_barber,
                requested_date=chosen_date,
                requested_time=chosen_time,
                duration_minutes=60
            )
            # if success:
                # clear session after booking
                # sessions[session_id] = {"intent": None, "barber": None, "date": None, "time": None}
            return msg
        except Exception as e:
            return str(f"⚠️ Couldn't book appointment: {e}")

    # -------- VIEW --------
    elif intent == "view_appointments":
        try:
            apps = fu.get_appointments_for_user(user_email)
            if not apps:
                return "📅 You have no upcoming appointments."
            items = [f"{a['barberName']} on {a['date']} at {a['time']}" for a in apps]
            return "📅 Your appointments:\n" + "\n".join(items)
        except Exception as e:
            return str(f"⚠️ Couldn't fetch appointments: {e}")

    # -------- CANCEL --------
    elif intent == "cancel_appointment":
        try:
            success, msg = fu.cancel_latest_appointment(user_email)
            return msg
        except Exception as e:
            return f"⚠️ Couldn't cancel appointment: {e}"

    # -------- SMALL TALK --------
    elif intent == "small_talk":
        return "👋 Hi! How can I help you today?"

    # -------- UNKNOWN --------
    else:
        return "⚠️ Sorry, I couldn’t understand that."

# ---------------- FALLBACK REGEX ----------------
def regex_fallback(message: str):
    text = message.lower()
    if any(w in text for w in ["hello", "hi", "hey"]):
        return {"intent": "small_talk"}
    if any(w in text for w in ["service", "services", "offer", "offers", "prices", "pricing", "price", "menu"]):
        return {"intent": "list_services"}
    if any(w in text for w in ["barber", "barbers", "stylists", "stylist", "team", "worker", "workers"]):
        return {"intent": "list_barbers"}
    if any(w in text for w in ["book", "books", "bok", "set up", "reserve", "fix", "make", "schedule"]):
        return {"intent": "book_appointment"}
    if any(w in text for w in ["cancel", "delete", "remove", "drop"]):
        return {"intent": "cancel_appointment"}
    if any(w in text for w in ["view", "see", "upcoming", "show", "my appointments", "schedule"]):
        return {"intent": "view_appointments"}
    return {"intent": "small_talk"}

# ---------------- MODEL INFERENCE (returns REPLY STRING) ----------------
# Initialize once (requires HF token in your env: HUGGINGFACEHUB_API_TOKEN) 
# Check if HF_TOKEN is already set in environment 
hf_token = os.getenv("HF_TOKEN") 
if not hf_token: 
    # Try loading from .env if not found 
    load_dotenv() 
    hf_token = os.getenv("HF_TOKEN") 
    
# Final check 
if not hf_token: 
    raise EnvironmentError( "❌ Hugging Face API token not found. Please set HF_TOKEN or HUGGINGFACEHUB_API_TOKEN " "in your environment or in a .env file." ) 
else: 
    print("✅ Hugging Face token loaded successfully.") 

# Initialize client with token + model 
hf_client = InferenceClient( model="mistralai/Mistral-7B-Instruct-v0.2", token=hf_token ) 

def make_response_natural(user_message: str, bot_message: str) -> str: 
    """ Take the system response and rephrase it in a natural conversational way. """
    prompt = f""" You are a friendly AI barber assistant. 
    The user said: "{user_message}" 
    The system generated reply is: "{bot_message}" 
    Rewrite the system reply into a natural, conversational sentence. 
    Keep the meaning the same. 
    Do NOT add questions, explanations, or commentary. 
    Do NOT wrap the reply in quotes. 
    Only output the final reply text. """ 
    # Use chat completion (Mistral supports conversational API, not raw text_generation) 
    response = hf_client.chat.completions.create( 
        model="mistralai/Mistral-7B-Instruct-v0.2", 
        messages=[{"role": "user", "content": prompt}], 
        max_tokens=150, 
        temperature=0.7 ) 
    
    return response.choices[0].message.content


def predict_intent(text: str) -> str:
    # Tokenize
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True).to(DEVICE)

    # Forward pass
    with torch.no_grad():
        outputs = model(**inputs)

    # Prediction
    logits = outputs.logits
    predicted_class_id = torch.argmax(logits, dim=-1).item()
    return id2label[predicted_class_id]


def chatbot_fn(message, session_id="default"):
 
    print(predict_intent(message))
    intent = predict_intent(message)

    # Guarantee fields exist (default null if missing)
    required_keys = ["intent", "barber", "date", "time"]
   
     # Always start with default dict
    parsed = {"intent": intent, "barber": None, "date": None, "time": None}

    # Fallback / guard-rails
    if parsed.get("intent") is None:
        parsed = regex_fallback(message)
        for k in required_keys:
            parsed.setdefault(k, None)

    # Route & return final reply STRING
    # reply = route_intent(parsed, message, session_id=session_id, user_email=session_id or "demo@example.com")
    raw_reply = route_intent(parsed, message, session_id=session_id, user_email=session_id or "demo@example.com")
    final_reply = make_response_natural(message, raw_reply)
    return final_reply
    # return str(reply)

# ---------------- GRADIO UI ----------------
with gr.Blocks(css="""
.gradio-container {max-width: 900px; margin: auto;}
.chat-header {
    display: flex; align-items: center; justify-content: flex-start;
    background: #007bff; color: white; padding: 12px; border-radius: 8px 8px 0 0;
    font-weight: bold; font-size: 18px;
}
.chat-header img {
    height: 32px; width: 32px; margin-right: 10px; border-radius: 50%;
}
""") as demo:
    gr.Markdown("## 💈 AI Barber Shop Chatbot")

    # --- STATE ---
    user_email = gr.State("")
    

    # --- LOGIN PAGE ---
    with gr.Row(visible=True) as login_row:
        with gr.Column():
            gr.Markdown("### 🔑 Login")
            email_box = gr.Textbox(label="Enter your email", placeholder="you@example.com")
            login_btn = gr.Button("Login")
    login_status = gr.Markdown()

    # --- CHATBOT PAGE ---
    with gr.Row(visible=False) as chat_row:
        with gr.Column(scale=3):
            with gr.Row(elem_classes="chat-header"):
                gr.Image("https://cdn-icons-png.flaticon.com/512/921/921087.png",
                         elem_classes="logo", show_label=False, show_download_button=False)
                gr.Markdown("AI Barber Assistant", elem_classes="title")

            # chatbot = gr.Chatbot(height=420, show_copy_button=True)
            chatbot = gr.Chatbot([], height=420, show_copy_button=True)
            msg = gr.Textbox(
                placeholder="Type your message and press Enter...",
                show_label=False
            )
            with gr.Row():
                send = gr.Button("Send")
                # clear = gr.Button("Clear Chat")

        # OPTIONAL SIDE PANEL (read-only)
        with gr.Column(scale=1, visible=True) as side_panel:
            gr.Markdown("### 💇 Services")
            # services_box = gr.Dataframe(headers=["Service", "Price"], interactive=False)
            services_box = gr.Dataframe(
                headers=["Service", "Price"],
                datatype=["str", "str"],   # explicitly set column types
                interactive=False
                )


            
            gr.Markdown("### ✂️ Barbers")
            # barbers_box = gr.Dataframe(headers=["Barber", "Speciality"], interactive=False)
            barbers_box = gr.Dataframe(
                headers=["Barber", "Speciality"],
                datatype=["str", "str"],   # explicitly set column types
                interactive=False
                )
            refresh_btn = gr.Button("🔄 Refresh Data")

    # --- FUNCTIONS ---
    def do_login(email):
        if not email or "@" not in email:
            return gr.update(value="❌ Please enter a valid email."), gr.update(visible=True), gr.update(visible=False), ""
        return (
            gr.update(value=f"✅ Logged in as {email}"),
            gr.update(visible=False),
            gr.update(visible=True),
            email
        )

    login_btn.click(
        do_login,
        inputs=email_box,
        outputs=[login_status, login_row, chat_row, user_email]
    )

    def load_data():
        try:
            services = fu.get_all_services()
            if not isinstance(services, list):
                services = []
            s_rows = [[s.get("name", ""), f"{s.get('price','')} PKR"] for s in services] or [["-", "-"]]

            barbers = fu.get_all_barbers()
            if not isinstance(barbers, list):
                barbers = []
            b_rows = [[b.get("name",""), b.get("speciality","")] for b in barbers] or [["-", "-"]]

            return s_rows, b_rows
        except Exception as e:
            err = [["Error", str(e)]]
            return err, err


    refresh_btn.click(load_data, None, [services_box, barbers_box])

    def respond(user_message, chat_history, email):
        # email also doubles as session_id for per-user sessions
        session_id = email or "default"
        reply = chatbot_fn(user_message, session_id=session_id)

        # Gradio Chatbot expects list of (user, bot) tuples
        chat_history = chat_history + [(user_message, reply)]
        return chat_history, ""  # clear input
    
    def respond(user_message, chat_history, email):
        if chat_history is None:
            chat_history = []
        session_id = email or "default"
        reply = chatbot_fn(user_message, session_id=session_id)
        chat_history.append((str(user_message), str(reply)))  # ensure strings
        return chat_history, ""  # clear input box
    msg.submit(respond, [msg, chatbot, user_email], [chatbot, msg])
    send.click(respond, [msg, chatbot, user_email], [chatbot, msg])
    # clear.click(lambda: [], None, chatbot, queue=False)

if __name__ == "__main__":
    demo.launch(share=True)
