import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud import firestore as gcf
from datetime import datetime, timedelta
import pytz
import re
import os, json

# ---------------------- Timezone ---------------------- #
TZ = pytz.timezone("Asia/Karachi")
from dotenv import load_dotenv

# ---------------------- Firebase Setup ---------------------- #
try:
    if not firebase_admin._apps:

        firebase_json = os.getenv("FIREBASE_CREDENTIALS")
        if not firebase_json:
            # Try loading from .env if not found
            load_dotenv()
            firebase_json = os.getenv("FIREBASE_CREDENTIALS")
        cred_dict = json.loads(firebase_json)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)

    db = firestore.client()
except Exception as e:
    raise RuntimeError(f"❌ Failed to initialize Firebase: {e}")

# ---------------------- Firestore Utilities ---------------------- #

def get_barber_by_id(barber_id: str):
    try:
        doc = db.collection("barbers").document(barber_id).get()
        if doc.exists:
            return doc.id, doc.to_dict()
        return None, None
    except Exception as e:
        return None, f"❌ Error fetching barber: {e}"

def get_first_barber():
    try:
        barbers = db.collection("barbers").limit(1).stream()
        for doc in barbers:
            return doc.id, doc.to_dict()
        return None, None
    except Exception as e:
        return None, f"❌ Error fetching barber: {e}"

def create_barber(barber_data: dict):
    try:
        ref = db.collection("barbers").document()  # auto-ID
        ref.set(barber_data)
        return ref.id
    except Exception as e:
        return f"❌ Error creating barber: {e}"

def get_appointments_for_barber_on_date(barber_id: str, date: str):
    try:
        snapshot = db.collection("appointments") \
            .where("barberId", "==", barber_id) \
            .where("date", "==", date).stream()
        return [doc.to_dict() for doc in snapshot]
    except Exception as e:
        return f"❌ Error fetching appointments: {e}"

def add_document(collection: str, data: dict, doc_id: str = None):
    try:
        if doc_id:
            db.collection(collection).document(doc_id).set(data)
            return doc_id
        else:
            ref = db.collection(collection).document()
            ref.set(data)
            return ref.id
    except Exception as e:
        return f"❌ Error adding document: {e}"

def get_all_barbers():
    try:
        barbers_ref = db.collection("barbers")
        docs = barbers_ref.stream()
        barbers = []
        for doc in docs:
            data = doc.to_dict()
            if "name" in data:
                barbers.append({"name": data["name"], **data})
        return barbers
    except Exception as e:
        print(f"Error fetching barbers: {e}")
        return []

def get_all_services():
    try:
        services_ref = db.collection("services")
        docs = services_ref.stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        print(f"Error fetching services: {e}")
        return []

def get_all_appointments():
    try:
        docs = db.collection("appointments").stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        print("Error fetching appointments:", e)
        return []

def get_appointments_for_user(user_email):
    docs = db.collection("appointments").where("userId", "==", user_email).get()
    return [d.to_dict() for d in docs]

# ---------------------- Helpers ---------------------- #

def add_minutes(time_str: str, minutes: int) -> str:
    time = datetime.strptime(time_str, "%H:%M")
    new_time = time + timedelta(minutes=minutes)
    return new_time.strftime("%H:%M")

def is_overlapping(start1, end1, start2, end2) -> bool:
    fmt = "%H:%M"
    s1 = datetime.strptime(start1, fmt)
    e1 = datetime.strptime(end1, fmt)
    s2 = datetime.strptime(start2, fmt)
    e2 = datetime.strptime(end2, fmt)
    return not (e1 <= s2 or s1 >= e2)

# ---------------------- Scheduling Constants ---------------------- #
SLOT_STEP_MIN = 15
LEAD_TIME_MIN = 15
MAX_LOOKAHEAD_DAYS = 30

# ---------------------- Improved Booking Logic ---------------------- #

def _now_local():
    return datetime.now(TZ)

def _to_dt(date_str, time_str):
    return TZ.localize(datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M"))

def _time_add(t_str, minutes):
    return add_minutes(t_str, minutes)

def _iter_slots(day_start, day_end, step_min=SLOT_STEP_MIN, duration=60):
    fmt = "%H:%M"
    cur = datetime.strptime(day_start, fmt)
    end = datetime.strptime(day_end, fmt)
    while cur + timedelta(minutes=duration) <= end:
        yield cur.strftime(fmt)
        cur += timedelta(minutes=step_min)

def _overlaps(s1, dur1, s2, dur2):
    fmt = "%H:%M"
    a1 = datetime.strptime(s1, fmt); b1 = a1 + timedelta(minutes=dur1)
    a2 = datetime.strptime(s2, fmt); b2 = a2 + timedelta(minutes=dur2)
    return (a1 < b2) and (a2 < b1)

def is_valid_time(requested_date, requested_time, duration_minutes, barber_data, existing_appointments):
    if not requested_date or not requested_time:
        return False, "❌ Missing date or time."

    now = _now_local()
    start_dt = _to_dt(requested_date, requested_time)
    if start_dt < now + timedelta(minutes=LEAD_TIME_MIN):
        return False, f"❌ Too soon. Minimum lead time is {LEAD_TIME_MIN} minutes."

    wh = barber_data.get("workingHours", {"start":"10:00","end":"22:00"})
    open_t, close_t = wh.get("start","10:00"), wh.get("end","22:00")
    appt_end = _time_add(requested_time, duration_minutes)
    if (datetime.strptime(requested_time, "%H:%M") < datetime.strptime(open_t, "%H:%M") or
        datetime.strptime(appt_end, "%H:%M") > datetime.strptime(close_t, "%H:%M")):
        return False, "❌ Outside working hours."

    bt = barber_data.get("breakTimes", None)
    if bt:
        bs, be = bt.get("start"), bt.get("end")
        if bs and be and is_overlapping(requested_time, appt_end, bs, be):
            return False, "❌ Overlaps with break time."

    for appt in existing_appointments or []:
        if appt.get("status") == "cancelled":
            continue
        ex_start = appt.get("time")
        ex_dur = int(appt.get("duration", 60))
        if _overlaps(requested_time, duration_minutes, ex_start, ex_dur):
            return False, "❌ Time slot already booked."

    return True, "✅ Time is available."

def find_next_available_slot(barber_id, duration_minutes=60, max_days=MAX_LOOKAHEAD_DAYS):
    now = _now_local()
    today = now.date()

    bdoc = db.collection("barbers").document(barber_id).get()
    if not bdoc.exists: return None
    bdata = bdoc.to_dict()

    for d in range(max_days + 1):
        day = today + timedelta(days=d)
        day_str = day.strftime("%Y-%m-%d")

        wh = bdata.get("workingHours", {"start":"10:00","end":"22:00"})
        open_t, close_t = wh.get("start","10:00"), wh.get("end","22:00")

        existing = get_appointments_for_barber_on_date(barber_id, day_str)
        if isinstance(existing, str): continue

        start_scan = open_t
        if d == 0:
            start_candidate = now + timedelta(minutes=LEAD_TIME_MIN)
            rounded = start_candidate.replace(second=0, microsecond=0)
            minute_over = rounded.minute % SLOT_STEP_MIN
            if minute_over:
                rounded += timedelta(minutes=(SLOT_STEP_MIN - minute_over))
            start_scan = max(open_t, rounded.strftime("%H:%M"))

        for t in _iter_slots(start_scan, close_t, SLOT_STEP_MIN, duration_minutes):
            ok, _ = is_valid_time(day_str, t, duration_minutes, bdata, existing)
            if ok:
                return (day_str, t)
    return None

def book_appointment(user_email, barber_name=None, service_name=None,
                     requested_date=None, requested_time=None, duration_minutes=60):
    """
    Handles all cases: date+time, date only, time only, ASAP.
    """
    def norm_date(d):
        if not d: return None
        if isinstance(d, datetime): return d.strftime("%Y-%m-%d")
        for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
            try: return datetime.strptime(str(d), fmt).strftime("%Y-%m-%d")
            except: pass
        return str(d)

    def norm_time(t):
        if t is None: return None
        t = str(t).strip().lower()
        if t in ("", "asap", "as soon as possible"): return None
        m = re.match(r"^\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*$", t)
        if not m:
            return t if re.match(r"^\d{2}:\d{2}$", t) else None
        hour = int(m.group(1)); minute = int(m.group(2) or 0); meridian = m.group(3)
        if meridian == "pm" and hour != 12: hour += 12
        if meridian == "am" and hour == 12: hour = 0
        return f"{hour:02d}:{minute:02d}"

    requested_date = norm_date(requested_date)
    requested_time = norm_time(requested_time)

    try:
        service_id = None
        if service_name:
            q = db.collection("services").where("name", "==", service_name).limit(1).get()
            if q: service_id = q[0].id

        barbers = db.collection("barbers").get()
        if not barbers: return False, "❌ No barbers found."

        chosen = None
        if barber_name:
            key = barber_name.strip().lower()
            for b in barbers:
                if b.to_dict().get("name", "").strip().lower() == key:
                    chosen = b; break
            if not chosen: return False, f"❌ Barber '{barber_name}' not found."

        final_date = final_time = None
        final_barber = None

        # A) date+time provided
        if requested_date and requested_time:
            target_barbers = [chosen] if chosen else barbers
            for b in target_barbers:
                existing = get_appointments_for_barber_on_date(b.id, requested_date)
                if isinstance(existing, str): continue
                ok, msg = is_valid_time(requested_date, requested_time, duration_minutes, b.to_dict(), existing)
                if ok:
                    final_date, final_time, final_barber = requested_date, requested_time, b
                    break
            if not final_barber: return False, "❌ No barber available at that date/time."

        # B) date only
        elif requested_date:
            target_barbers = [chosen] if chosen else barbers
            for b in target_barbers:
                wh = b.to_dict().get("workingHours", {"start":"10:00","end":"22:00"})
                open_t, close_t = wh.get("start","10:00"), wh.get("end","22:00")
                existing = get_appointments_for_barber_on_date(b.id, requested_date)
                if isinstance(existing, str): continue
                for t in _iter_slots(open_t, close_t, SLOT_STEP_MIN, duration_minutes):
                    ok, _ = is_valid_time(requested_date, t, duration_minutes, b.to_dict(), existing)
                    if ok:
                        final_date, final_time, final_barber = requested_date, t, b
                        break
                if final_barber: break
            if not final_barber: return False, f"❌ No free slots on {requested_date}."

        # C) time only
        elif requested_time:
            target_barbers = [chosen] if chosen else barbers
            for b in target_barbers:
                for delta in range(MAX_LOOKAHEAD_DAYS + 1):
                    d = (_now_local() + timedelta(days=delta)).strftime("%Y-%m-%d")
                    existing = get_appointments_for_barber_on_date(b.id, d)
                    if isinstance(existing, str): continue
                    ok, _ = is_valid_time(d, requested_time, duration_minutes, b.to_dict(), existing)
                    if ok:
                        final_date, final_time, final_barber = d, requested_time, b
                        break
                if final_barber: break
            if not final_barber: return False, f"❌ No barbers free at {requested_time} in next {MAX_LOOKAHEAD_DAYS} days."

        # D) ASAP
        else:
            target_barbers = [chosen] if chosen else barbers
            slots = []
            for b in target_barbers:
                slot = find_next_available_slot(b.id, duration_minutes)
                if slot: slots.append((slot[0], slot[1], b))
            if not slots: return False, "❌ Couldn’t find any available barber in the next 30 days."
            final_date, final_time, final_barber = sorted(slots, key=lambda x: (x[0], x[1]))[0]

        if not (final_date and final_time and final_barber):
            return False, "❌ Could not resolve a valid date/time/barber."

        existing = get_appointments_for_barber_on_date(final_barber.id, final_date)
        if isinstance(existing, str): return False, existing
        ok, msg = is_valid_time(final_date, final_time, duration_minutes, final_barber.to_dict(), existing)
        if not ok: return False, msg

        fmt = "%H:%M"
        new_start = datetime.strptime(final_time, fmt)
        new_end = new_start + timedelta(minutes=duration_minutes)
        user_same_day = db.collection("appointments") \
                          .where("userId", "==", user_email) \
                          .where("date", "==", final_date).get()
        for appt in user_same_day:
            d = appt.to_dict()
            if d.get("status") == "cancelled": continue
            ex_start = datetime.strptime(d["time"], fmt)
            ex_end = ex_start + timedelta(minutes=d.get("duration", 60))
            if (new_start < ex_end) and (ex_start < new_end):
                return False, "⚠️ You already have an overlapping appointment."

        barber_display = final_barber.to_dict().get("name")
        new_appt = {
            "userId": user_email,
            "barberId": final_barber.id,
            "barberName": barber_display,
            "serviceId": service_id,
            "serviceName": service_name,
            "date": final_date,
            "time": final_time,
            "duration": duration_minutes,
            "status": "booked",
            "createdAt": gcf.SERVER_TIMESTAMP,
            "updatedAt": gcf.SERVER_TIMESTAMP
        }
        db.collection("appointments").add(new_appt)
        return True, f"✅ Appointment booked with {barber_display} on {final_date} at {final_time}"

    except Exception as e:
        return False, f"❌ Error booking appointment: {str(e)}"

# ---------------------- Appointment Views / Cancel ---------------------- #

def view_appointments(user_email):
    try:
        snapshot = db.collection("appointments") \
            .where("userId", "==", user_email) \
            .order_by("date") \
            .order_by("time") \
            .stream()
        return [doc.to_dict() for doc in snapshot]
    except Exception as e:
        return f"❌ Error viewing appointments: {e}"

def cancel_latest_appointment(user_email):
    docs = db.collection("appointments") \
         .where("userId", "==", user_email) \
         .where("status", "==", "booked") \
         .get()

    if not docs:
        return False, "❌ You have no active appointments to cancel."

    # Sort by date and time in Python
    latest_doc = sorted(docs, key=lambda d: (d.get("date"), d.get("time")), reverse=True)[0]
    latest_doc.reference.delete()
    
    return True, "✅ Your latest appointment has been cancelled."


# ---------------------- Suggestions ---------------------- #

def suggest_alternatives(barber_id, date_str, time_str=None, duration_minutes=60, limit=3):
    """
    Suggest up to `limit` next valid slots (date, time) for a given barber,
    starting at the requested date/time. If time_str is None, starts from the day's opening.
    """
    try:
        barber_doc = db.collection("barbers").document(barber_id).get()
        if not barber_doc.exists:
            return []

        bdata = barber_doc.to_dict()
        collected = []
        now = _now_local()

        # --- scan same day first ---
        wh = bdata.get("workingHours", {"start":"10:00","end":"22:00"})
        open_t, close_t = wh.get("start","10:00"), wh.get("end","22:00")
        start_scan = time_str or open_t
        existing = get_appointments_for_barber_on_date(barber_id, date_str)
        if not isinstance(existing, str):
            for t in _iter_slots(start_scan, close_t, SLOT_STEP_MIN, duration_minutes):
                dt = _to_dt(date_str, t)
                if dt < now + timedelta(minutes=LEAD_TIME_MIN):
                    continue
                ok, _ = is_valid_time(date_str, t, duration_minutes, bdata, existing)
                if ok:
                    collected.append((date_str, t))
                    if len(collected) >= limit:
                        return collected

        # --- scan future days ---
        day = datetime.strptime(date_str, "%Y-%m-%d").date()
        for step in range(1, MAX_LOOKAHEAD_DAYS + 1):
            if len(collected) >= limit:
                break
            d = (day + timedelta(days=step)).strftime("%Y-%m-%d")
            existing2 = get_appointments_for_barber_on_date(barber_id, d)
            if isinstance(existing2, str):
                continue
            wh2 = bdata.get("workingHours", {"start":"10:00","end":"22:00"})
            open2, close2 = wh2.get("start","10:00"), wh2.get("end","22:00")
            for t in _iter_slots(open2, close2, SLOT_STEP_MIN, duration_minutes):
                ok, _ = is_valid_time(d, t, duration_minutes, bdata, existing2)
                if ok:
                    collected.append((d, t))
                    if len(collected) >= limit:
                        break
        return collected
    except Exception as e:
        print(f"Error suggesting alternatives: {e}")
        return []
