"""
Automated smoke test — teenon agents ke tools bina LLM ke test karta hai.
Data files ko backup karke restore karta hai, taaki asli data kharab na ho.

Run:  python smoke_test.py
Exit code 0 = sab PASS, 1 = kuch FAIL.
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
BACKUP = "/tmp/voice_agents_backup"

passed, failed = [], []


def check(name, cond, detail=""):
    (passed if cond else failed).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail and not cond else ""))


def backup():
    if os.path.exists(BACKUP):
        shutil.rmtree(BACKUP)
    shutil.copytree(DATA, BACKUP)


def restore():
    shutil.rmtree(DATA)
    shutil.copytree(BACKUP, DATA)


def main():
    from tools_impl import (
        book_appointment,
        check_slots,
        save_callback,
        save_lead,
        search_faq,
    )

    backup()
    try:
        print("Booking tools:")
        r = check_slots("2026-09-22")
        check("check_slots khaali slots deta hai", "10:00" in r, r)
        r = check_slots("2099-01-01")
        check("check_slots khaali date pe mana karta hai", "khaali nahi" in r, r)
        r = book_appointment("Test User", "9999999999", "2026-09-22", "10:00")
        check("book_appointment book karta hai", "book ho gayi" in r, r)
        r = check_slots("2026-09-22")
        check("booked slot list se hatta hai", "10:00" not in r, r)
        r = book_appointment("Test User", "9999999999", "2026-09-22", "10:00")
        check("double booking rokta hai", "khaali nahi" in r, r)

        print("Support tools:")
        r = search_faq("refund kaise milega")
        check("search_faq jawab dhundta hai", r != "NO_ANSWER", r)
        r = search_faq("mera printer blast ho gaya xyz")
        check("search_faq anjaan sawal pe NO_ANSWER", r == "NO_ANSWER", r)
        r = save_callback("Test User", "9999999999", "ajeeb problem")
        check("save_callback note karta hai", "note kar li" in r, r)

        print("Lead tools:")
        r = save_lead("Test User", "9999999999", "website", "50000", "1 mahina")
        check("save_lead save karta hai", "save ho gayi" in r, r)
        with open(os.path.join(DATA, "leads.csv"), encoding="utf-8") as f:
            content = f.read()
        check("leads.csv me entry hai", "Test User" in content and "website" in content)

        print("Validation (junk data reject hona chahiye):")
        r = save_lead("[name]", "[phone]", "website", "50000", "1 mahina")
        check("save_lead placeholder reject karta hai", "save nahi hui" in r, r)
        r = save_lead("Nishant", "?", "website", "50000", "1 mahina")
        check("save_lead bina phone reject karta hai", "save nahi hui" in r, r)
        r = save_callback("??", "123", "problem")
        check("save_callback junk reject karta hai", "note nahi hui" in r, r)
        r = book_appointment("N", "9999999999", "2026-09-22", "15:00")
        check("book_appointment junk naam reject karta hai", "nahi hui" in r, r)

        print("Agents config:")
        from agents import AGENTS

        for key in ("booking", "support", "lead"):
            a = AGENTS.get(key, {})
            check(f"agent '{key}' ka prompt+tools hai",
                  bool(a.get("system_prompt")) and bool(a.get("tools")) and bool(a.get("greeting")))
    finally:
        restore()

    print(f"\n{len(passed)} passed, {len(failed)} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
