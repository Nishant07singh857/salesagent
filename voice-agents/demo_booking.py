"""
BOOKING AGENT — End-to-End Demo (bina Twilio / API keys ke)

Run:  python demo_booking.py
"""
import datetime
import re

from demo_common import parse_phone, run_demo
from tools_impl import book_appointment, check_slots

WEEKDAYS = {
    "monday": 0, "somvar": 0, "somvaar": 0,
    "tuesday": 1, "mangalvar": 1, "mangal": 1,
    "wednesday": 2, "budhvar": 2, "budh": 2,
    "thursday": 3, "guruwar": 3, "guruvar": 3,
    "friday": 4, "shukravar": 4, "shukrvar": 4,
    "saturday": 5, "shanivar": 5,
    "sunday": 6, "ravivar": 6, "itvar": 6,
}


def parse_date(text):
    t = text.strip().lower()
    today = datetime.date.today()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            return None
    if "parso" in t:
        return (today + datetime.timedelta(days=2)).isoformat()
    if "kal" in t:
        return (today + datetime.timedelta(days=1)).isoformat()
    if "aaj" in t:
        return today.isoformat()
    for name, wd in WEEKDAYS.items():
        if name in t:
            delta = (wd - today.weekday()) % 7
            return (today + datetime.timedelta(days=delta)).isoformat()
    return None


def parse_time(text, offered):
    m = re.search(r"(\d{1,2})(?::(\d{2}))?", text)
    if not m:
        return None
    hh = m.group(1).zfill(2)
    cand = f"{hh}:{m.group(2) or '00'}"
    if cand in offered:
        return cand
    for s in offered:
        if s.startswith(hh + ":"):
            return s
    return None


class BookingFlow:
    """Bina LLM ke demo dimaag — booking ka poora flow, asli tools ke saath."""

    def __init__(self):
        self.name = None
        self.date = None
        self.time = None
        self.phone = None
        self.offered = []

    def reply(self, user_text):
        t = user_text.strip()

        if not self.name:
            self.name = t
            return (f"Achha {t}, samajh gaya. Kaunsi date pe appointment chahiye? "
                    f"'kal', 'parso' ya YYYY-MM-DD me batao."), False

        if not self.date:
            d = parse_date(t)
            if not d:
                return ("Hmm, date samajh nahi aayi. 'kal', 'parso' bolo "
                        "ya YYYY-MM-DD format me likho."), False
            self.date = d
            print(f'  [tool] check_slots(date="{d}") chala...')
            result = check_slots(d)
            print(f"  [tool] → {result}")
            if "khaali slots" not in result:
                self.date = None
                return f"Hmm, {d} ko koi slot khaali nahi hai. Koi aur date batao?", False
            self.offered = re.findall(r"\d{2}:\d{2}", result)
            return (f"{d} ko ye slots khaali hain: {', '.join(self.offered)}. "
                    f"Kaunsa time chahiye?"), False

        if not self.time:
            tm = parse_time(t, self.offered)
            if not tm:
                return (f"Ye time available nahi hai. "
                        f"Inme se chuno: {', '.join(self.offered)}"), False
            self.time = tm
            return (f"{tm} baje, note kar liya. Ab apna phone number batao "
                    f"taaki confirmation bhej saku."), False

        ph = parse_phone(t)
        if not ph:
            return "Phone number samajh nahi aaya, 10 digit ka number batao.", False
        self.phone = ph
        print(f'  [tool] book_appointment(name="{self.name}", phone="{ph}", '
              f'date="{self.date}", time="{self.time}") chala...')
        result = book_appointment(self.name, ph, self.date, self.time)
        print(f"  [tool] → {result}")
        return f"{result} Kuch aur madad chahiye?", True


if __name__ == "__main__":
    run_demo("booking", BookingFlow, "BOOKING AGENT — END-TO-END DEMO")
