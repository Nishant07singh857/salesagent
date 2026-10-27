"""
Agents ke tools ka asli implementation.
Abhi local JSON/CSV files use ho rahi hain — baad me yahi functions
Google Calendar / database se connect kar dena, agents.py nahi badlega.

Har tool apne inputs validate karta hai. Kuch galat/adhoora mile to
LLM ko wapas bhejta hai ki caller se kya puchna hai — taaki junk data
kabhi save na ho.
"""
import csv
import json
import os
import re

DATA = os.path.join(os.path.dirname(__file__), "data")


def _clean(v):
    return (v or "").strip()


def _valid_contact(name, phone):
    """
    Returns ((name, phone10), None) agar sahi hai,
    warna (None, error_msg) — LLM ye msg padhke caller se dobara puchega.
    """
    name = _clean(name)
    phone = re.sub(r"\D", "", _clean(phone))
    if len(name) < 2 or any(c in name for c in "[]?*"):
        return None, "naam sahi nahi mila — caller se naam pucho"
    if len(phone) < 10:
        return None, "10 digit ka phone number nahi mila — caller se number pucho"
    return (name, phone[-10:]), None


def _load_json(name, default):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_json(name, obj):
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def check_slots(date: str) -> str:
    slots = _load_json("slots.json", {})
    free = slots.get(date, [])
    if not free:
        return f"{date} ko koi slot khaali nahi hai."
    return f"{date} ko khaali slots: {', '.join(free)}"


def book_appointment(name: str, phone: str, date: str, time: str) -> str:
    contact, err = _valid_contact(name, phone)
    if err:
        return f"Booking nahi hui: {err}."
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", _clean(date)):
        return "Booking nahi hui: date YYYY-MM-DD format me nahi hai — caller se date pucho."
    name, phone = contact
    slots = _load_json("slots.json", {})
    free = slots.get(date, [])
    if time not in free:
        return f"Sorry, {date} ko {time} ab khaali nahi hai. Koi aur time try karo."
    free.remove(time)
    slots[date] = free
    _save_json("slots.json", slots)

    bookings = _load_json("bookings.json", [])
    bookings.append({"name": name, "phone": phone, "date": date, "time": time})
    _save_json("bookings.json", bookings)
    return f"Ho gaya! {name} ki appointment {date} ko {time} baje book ho gayi."


def search_faq(query: str) -> str:
    path = os.path.join(DATA, "faq.md")
    if not os.path.exists(path):
        return "Knowledge base khaali hai."
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    # Simple keyword match: sawal ke shabd FAQ lines me dhundo
    keywords = [w.strip("?,.!").lower() for w in query.split() if len(w) > 3]
    best, best_score = "", 0
    for line in lines:
        low = line.lower()
        score = sum(1 for k in keywords if k in low)
        if score > best_score:
            best, best_score = line, score
    if best_score == 0:
        return "NO_ANSWER"
    return best


def save_callback(name: str, phone: str, issue: str) -> str:
    contact, err = _valid_contact(name, phone)
    if err:
        return f"Callback note nahi hui: {err}."
    if not _clean(issue):
        return "Callback note nahi hui: problem kya hai ye pata nahi — caller se pucho."
    name, phone = contact
    _append_lead_row([name, phone, f"CALLBACK: {_clean(issue)}", "", ""])
    return f"Callback request note kar li: {name} ({phone})"


def save_lead(name: str, phone: str, need: str, budget: str, timeline: str) -> str:
    contact, err = _valid_contact(name, phone)
    if err:
        return f"Lead save nahi hui: {err}."
    if not _clean(need):
        return "Lead save nahi hui: customer ko kya chahiye ye pata nahi — pucho."
    name, phone = contact
    _append_lead_row([name, phone, _clean(need), _clean(budget), _clean(timeline)])
    return f"Lead save ho gayi: {name} ({phone})"


def _append_lead_row(row):
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, "leads.csv")
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["name", "phone", "need", "budget", "timeline"])
        w.writerow(row)


def dispatch(tool_name: str, args: dict) -> str:
    """LLM ke tool call ko sahi function pe bhejo."""
    fn = {
        "check_slots": check_slots,
        "book_appointment": book_appointment,
        "search_faq": search_faq,
        "save_callback": save_callback,
        "save_lead": save_lead,
    }.get(tool_name)
    if not fn:
        return f"Unknown tool: {tool_name}"
    try:
        return str(fn(**args))
    except Exception as e:  # noqa: BLE001 — caller ko simple message do
        return f"Tool me error aaya: {e}"
