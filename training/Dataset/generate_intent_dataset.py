# generate_intent_dataset.py
import json, random, re, argparse, os
from datetime import datetime, timedelta
import pytz
from collections import defaultdict

# ---------------- Firebase + Fallback ----------------
def load_entities_from_firebase():
    barbers, services = [], []
    for modpath in ("Firebase.firebase_utils", "firebase_utils"):
        try:
            fu = __import__(modpath, fromlist=['*'])
            try:
                b_list = fu.get_all_barbers()
                if isinstance(b_list, list) and b_list:
                    barbers = [b.get("name") for b in b_list if b.get("name")]
            except Exception:
                pass
            try:
                s_list = fu.get_all_services()
                if isinstance(s_list, list) and s_list:
                    for s in s_list:
                        nm = s.get("name")
                        pr = s.get("price", None)
                        if nm:
                            services.append({"name": nm, "price": pr})
            except Exception:
                pass
            break
        except Exception:
            continue
    return barbers, services

def fallback_entities():
    barbers = ["Imran Barber", "Ali Barber", "Sara Stylist", "Hamza Barber"]
    services = [
        {"name": "Haircut", "price": 500},
        {"name": "Beard Trim", "price": 300},
        {"name": "Shave", "price": 350},
        {"name": "Haircut + Beard", "price": 750},
    ]
    return barbers, services

def ensure_entities():
    b, s = load_entities_from_firebase()
    fb_b, fb_s = fallback_entities()
    if not b: b = fb_b
    if not s: s = fb_s
    return b, s

# ---------------- Utilities ----------------
TZ = pytz.timezone("Asia/Karachi")

BOOK_SYNS = ["book", "schedule", "set up", "arrange", "reserve", "fix", "make","bok"]
ASK_SERVICE_SYNS = ["services", "service list", "what do you offer", "prices", "pricing", "menu"]
ASK_BARBER_SYNS = ["barbers", "barber list", "stylists", "who works there", "team"]
VIEW_SYNS = ["my appointments", "upcoming appointments", "do i have anything booked", "what do i have", "view appointments"]
CANCEL_SYNS = ["cancel", "call off", "drop", "remove my booking", "scrap my appointment"]
SMALL_TALK = ["hey", "hello", "hi there", "how are you", "thanks", "cool", "great", "who are you", "good morning", "good evening"]

DATE_VERBAL = ["today", "tomorrow"]
DOWS = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]

def next_weekday(target_name, today=None):
    if today is None:
        today = datetime.now(TZ).date()
    target = DOWS.index(target_name.lower())
    delta = (target - today.weekday() + 7) % 7
    delta = 7 if delta == 0 else delta
    return today + timedelta(days=delta)

def random_future_date_str(max_days=45, min_days=1):
    base = datetime.now(TZ).date() + timedelta(days=random.randint(min_days, max_days))
    return base.strftime("%Y-%m-%d")

def pick_date_phrase():
    r = random.random()
    if r < 0.25:
        word = random.choice(DATE_VERBAL)
        date = datetime.now(TZ).date() + (timedelta(days=1) if word == "tomorrow" else timedelta(days=0))
        return word, date.strftime("%Y-%m-%d")
    elif r < 0.55:
        w = random.choice(DOWS)
        date = next_weekday(w)
        return f"next {w}", date.strftime("%Y-%m-%d")
    else:
        iso = random_future_date_str()
        return iso, iso

TIME_SLOTS_24 = [f"{h:02d}:{m:02d}" for h in range(10, 18) for m in (0, 30) if not (h == 13)]

def to_12h(t24):
    dt = datetime.strptime(t24, "%H:%M")
    return dt.strftime("%I:%M %p").lstrip("0")  # e.g., 2:30 PM (uppercase AM/PM)

def pick_time_phrase():
    r = random.random()
    if r < 0.35:
        slot = random.choice(["morning", "afternoon", "evening", "as soon as possible"])
        mapping = {"morning": "10:00", "afternoon": "14:00", "evening": "17:00", "as soon as possible": "10:00"}
        return slot, mapping[slot]
    elif r < 0.70:
        t24 = random.choice(TIME_SLOTS_24)
        return to_12h(t24), t24  # keep AM/PM uppercase
    else:
        t24 = random.choice(TIME_SLOTS_24)
        return t24, t24

def maybe_noise(text):
    tails = ["", "", "", " please", " thanks", " if possible", " asap"]
    punct = ["", ".", "!", "…"]
    return text + random.choice(tails) + random.choice(punct)

def pick_barber_phrase(barber):
    nick = barber.split()[0]
    variants = [barber, f"Mr {nick}", f"{nick}", f"with {barber}", f"with {nick}"]
    return random.choice(variants)

def pick_service_phrase(service_name):
    variants = [
        service_name, f"a {service_name}", f"{service_name} service",
        "a quick trim" if "haircut" in service_name.lower() else f"{service_name} please"
    ]
    return random.choice(variants)

# ---------------- Sample builders (now return {"text", "intent"}) ----------------
# def sample_book(barbers, services):
#     barber = random.choice(barbers)
#     service = random.choice(services)["name"] if services else "Haircut"
#     date_phrase, _date_norm = pick_date_phrase()
#     time_phrase, _time_norm = pick_time_phrase()

#     book_word = random.choice(BOOK_SYNS)
#     parts1 = [
#         random.choice(["I want to", "Can I", "Please", "I'd like to", "Help me"]).strip(),
#         book_word,
#         random.choice(["an appointment"
#                        , "a slot"
#                        #, pick_service_phrase(service)
#                        ])
#     ]
#     parts2 = [
#         book_word,        
#         random.choice(["an appointment"
#                        , "a slot"
#                        #, pick_service_phrase(service)
#                        ])
#     ]
#     with_part = random.choice(["with", "w/"])
#     bp = pick_barber_phrase(barber)
#     by_date = random.choice(["for", "on"])
#     at = random.choice(["at", "around"])
#     # randomly pick parts1 or parts2
#     parts = parts1 if random.randrange(0, 2) == 0 else parts2  

#     utter = f"{' '.join(parts)} {with_part} {bp} {by_date} {date_phrase} {at} {time_phrase}"

#     return {"text": maybe_noise(utter), "intent": "book_appointment"}
def sample_book(barbers, services):
    
    barber = random.choice(barbers)
    service = random.choice(services)["name"] if services else "Haircut"

    # --- NEW: sometimes skip barber/date/time to generate short forms ---
    if random.random() < 0.45:
        book_word = random.choice(BOOK_SYNS)  # <-- define book_word here
        parts = [
            book_word,
            random.choice([
                "me an appointment",
                f"a {service}",
                f"{service}",  # fixed leading space
                f"appointment for {service}",
                "a slot",
                "me an appoitnment",  # typo form
            ])
        ]
        utter = " ".join(parts)  # <-- join parts into a string
        return {"text": maybe_noise(utter), "intent": "book_appointment"}

    # --- existing long-form generation ---
    date_phrase, _ = pick_date_phrase()
    time_phrase, _ = pick_time_phrase()
    book_word = random.choice(BOOK_SYNS)
    parts = [
        random.choice(["I want to", "Can I", "I'd like to", "Help me", "Please"]).strip(),
        book_word,
        random.choice(["an appointment", "a slot", f"a {service}"])
    ]
    with_part = random.choice(["with", "w/"])
    bp = pick_barber_phrase(barber)
    by_date = random.choice(["for", "on"])
    at = random.choice(["at", "around"])
    utter = f"{' '.join(parts)} {with_part} {bp} {by_date} {date_phrase} {at} {time_phrase}"

    return {"text": maybe_noise(utter), "intent": "book_appointment"}


def sample_cancel(barbers):
    barber = random.choice(barbers)
    include_barber = random.random() < 0.5
    include_date = random.random() < 0.4
    date_phrase, _date_norm = pick_date_phrase() if include_date else (None, None)

    cancel_word = random.choice(CANCEL_SYNS)
    base = random.choice([
        f"please {cancel_word} my booking",
        f"{cancel_word} my appointment",
        f"{cancel_word} the reservation",
        f"can you {cancel_word} it"
    ])
    extra = []
    if include_barber:
        extra.append(f"with {barber.split()[0]}")
    if include_date:
        extra.append(f"for {date_phrase}")
    if extra:
        base += " " + " ".join(extra)
    return {"text": maybe_noise(base), "intent": "cancel_appointment"}

def sample_view():
    phr = random.choice(VIEW_SYNS + ["do i have anything tomorrow","what's on my schedule","show my bookings","list my appointments"])
    return {"text": maybe_noise(phr), "intent": "view_appointments"}

def sample_list_barbers():
    phr = random.choice(["show me barbers list","who are your barbers","list your stylists","how many barbers do you have","barber list please"])
    return {"text": maybe_noise(phr), "intent": "list_barbers"}

def sample_list_services():
    phr = random.choice(["tell me about your services","service list please","what do you offer","prices?","show me the menu","how much is a haircut"])
    return {"text": maybe_noise(phr), "intent": "list_services"}

def sample_small_talk():
    phr = random.choice(SMALL_TALK + ["can you help me","what can you do","who am i talking to","cool","ok thanks","sounds good"])
    return {"text": maybe_noise(phr), "intent": "small_talk"}

# Weighted mix (keeps ALL intents)
def make_one(barbers, services):
    r = random.random()
    if r < 0.55:   return sample_book(barbers, services)
    if r < 0.70:   return sample_cancel(barbers)
    if r < 0.82:   return sample_view()
    if r < 0.90:   return sample_list_barbers()
    if r < 0.98:   return sample_list_services()
    return sample_small_talk()

# ---------------- Stratified split ----------------
def stratified_split(data, val_ratio=0.1, seed=42):
    random.seed(seed)
    grouped = defaultdict(list)
    for ex in data:
        grouped[ex["intent"]].append(ex)

    train, val = [], []
    for intent, examples in grouped.items():
        n_val = max(1, int(len(examples) * val_ratio))
        random.shuffle(examples)
        val.extend(examples[:n_val])
        train.extend(examples[n_val:])
    random.shuffle(train)
    random.shuffle(val)
    return train, val

# ---------------- Main ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--total", type=int, default=15000, help="Total examples to generate")
    ap.add_argument("--val-ratio", type=float, default=0.1, help="Validation split ratio")
    ap.add_argument("--seed", type=int, default=42, help="Random seed")
    ap.add_argument("--out-train", default="intent_train.json")
    ap.add_argument("--out-val", default="intent_val.json")
    args = ap.parse_args()

    random.seed(args.seed)
    barbers, services = ensure_entities()
    if not barbers:
        raise SystemExit("No barbers available; please ensure Firebase or fallback works.")

    # Generate simplified examples: {"text": ..., "intent": ...}
    data = [make_one(barbers, services) for _ in range(args.total)]

    # Stratified split across ALL intents
    train, val = stratified_split(data, val_ratio=args.val_ratio, seed=args.seed)

    # Save as JSON arrays (matches your training script expectations)
    with open(args.out_train, "w", encoding="utf-8") as f:
        json.dump(train, f, ensure_ascii=False, indent=2)
    with open(args.out_val, "w", encoding="utf-8") as f:
        json.dump(val, f, ensure_ascii=False, indent=2)

    # Helpful counts per intent to verify none were missed
    def counts(split):
        c = defaultdict(int)
        for x in split:
            c[x["intent"]] += 1
        return dict(sorted(c.items()))
    print(f"Generated {len(train)} train and {len(val)} val examples (stratified).")
    print("Train intent counts:", counts(train))
    print("Val intent counts:  ", counts(val))
    print(f"Train file → {args.out_train}")
    print(f"Val file   → {args.out_val}")

if __name__ == "__main__":
    main()
