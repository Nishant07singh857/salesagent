"""
SUPPORT AGENT — End-to-End Demo (bina Twilio / API keys ke)

Run:  python demo_support.py

Try karo:
  1) "refund kaise milega" → FAQ se jawab milega
  2) "mera printer blast ho gaya" → jawab nahi milega → callback request note hogi
"""
from demo_common import parse_phone, run_demo
from tools_impl import save_callback, search_faq


class SupportFlow:
    """Bina LLM ke demo dimaag — FAQ search + callback, asli tools ke saath."""

    def __init__(self):
        self.stage = "issue"  # issue → resolved? → callback_name → callback_phone → done
        self.issue = None
        self.name = None

    def reply(self, user_text):
        t = user_text.strip()

        if self.stage == "issue":
            self.issue = t
            print(f'  [tool] search_faq(query="{t[:50]}") chala...')
            result = search_faq(t)
            print(f"  [tool] → {result[:90]}")
            if result == "NO_ANSWER":
                self.stage = "callback_name"
                return ("Hmm, iska jawab mere paas abhi nahi hai. Main aapki "
                        "callback request note kar leta hun — aapka naam kya hai?"), False
            self.stage = "resolved"
            return f"{result} Kya isse aapki problem solve ho gayi? (haan/naheen)", False

        if self.stage == "resolved":
            if any(w in t.lower() for w in ("haan", "yes", "ho gayi", "thik hai", "theek", "ok")):
                return "Bahut badhiya! Kuch aur madad chahiye to phir call kijiyega.", True
            self.stage = "callback_name"
            return ("Samajh gaya. Main aapki callback request note kar leta hun — "
                    "aapka naam kya hai?"), False

        if self.stage == "callback_name":
            self.name = t
            self.stage = "callback_phone"
            return f"Theek hai {t}. Apna phone number batao.", False

        ph = parse_phone(t)
        if not ph:
            return "Phone number samajh nahi aaya, 10 digit ka number batao.", False
        print(f'  [tool] save_callback(name="{self.name}", phone="{ph}", '
              f'issue="{self.issue[:40]}") chala...')
        result = save_callback(self.name, ph, self.issue)
        print(f"  [tool] → {result}")
        return f"{result} Hamari team jald callback karegi.", True


if __name__ == "__main__":
    run_demo("support", SupportFlow, "SUPPORT AGENT — END-TO-END DEMO")
