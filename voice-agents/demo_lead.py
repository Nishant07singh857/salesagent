"""
LEAD AGENT — End-to-End Demo (bina Twilio / API keys ke)

Run:  python demo_lead.py

Agent ek-ek karke 4 cheezein puchega: kya chahiye, budget, timeline, contact.
Sab milte hi lead data/leads.csv me save hogi.
"""
from demo_common import parse_phone, run_demo
from tools_impl import save_lead


class LeadFlow:
    """Bina LLM ke demo dimaag — lead qualification, asli tools ke saath."""

    def __init__(self):
        self.need = None
        self.budget = None
        self.timeline = None
        self.name = None

    def reply(self, user_text):
        t = user_text.strip()

        if not self.need:
            self.need = t
            return "Samajh gaya. Budget ka kuch idea hai?", False

        if not self.budget:
            self.budget = t
            return "Theek hai. Kab tak chahiye aapko ye?", False

        if not self.timeline:
            self.timeline = t
            return "Note kar liya. Aapka naam kya hai?", False

        if not self.name:
            self.name = t
            return f"Theek hai {t}. Phone number batao taaki hamari team contact kar sake.", False

        ph = parse_phone(t)
        if not ph:
            return "Phone number samajh nahi aaya, 10 digit ka number batao.", False
        print(f'  [tool] save_lead(name="{self.name}", phone="{ph}", ...) chala...')
        result = save_lead(self.name, ph, self.need, self.budget, self.timeline)
        print(f"  [tool] → {result}")
        return f"{result} Hamari team jald contact karegi. Dhanyavaad!", True


if __name__ == "__main__":
    run_demo("lead", LeadFlow, "LEAD AGENT — END-TO-END DEMO")
