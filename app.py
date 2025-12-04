import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import re

st.set_page_config(page_title="Website Outreach AI Agent", layout="wide")

# -------------------------
# Config / API
# -------------------------
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL_NAME = "llama-3.3-70b-versatile"

# ------------------------------------
# Smart Spam-Word Filter (simple map)
# ------------------------------------
spam_words_map = {
    r"(?i)\bbuy\b": "explore",
    r"(?i)\bbulk\b": "high-volume",
    r"(?i)\bemail list\b": "decision-maker contacts",
    r"(?i)\bguarantee\b": "support",
    r"(?i)\bcheap\b": "budget-friendly",
    r"(?i)\bfree leads\b": "sample contacts",
    r"(?i)\bpurchase\b": "access",
    r"(?i)\bno risk\b": "no pressure",
    r"(?i)\bspecial offer\b": "focused support",
    r"(?i)\bmarketing list\b": "targeted contacts",
    r"(?i)\brisk-free\b": "optional",
}

def smart_filter(text: str) -> str:
    """Replace risky spam-trigger words with safer alternatives."""
    for pattern, replacement in spam_words_map.items():
        text = re.sub(pattern, replacement, text)
    return text

# -------------------------
# Website Scraper
# -------------------------
def scrape_website(url: str) -> str:
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        return text[:4000]
    except Exception:
        return ""

# -------------------------
# Extract JSON Insights
# -------------------------
def extract_json(content: str):
    """
    Try to extract a JSON object substring from content and parse it.
    Returns dict or None.
    """
    if not content or not isinstance(content, str):
        return None
    try:
        # Find first '{' and last '}' and parse that substring
        start = content.find("{")
        end = content.rfind("}") + 1
        if start == -1 or end == 0:
            return None
        json_str = content[start:end]
        data = json.loads(json_str)
        # normalize expected fields if missing
        if "company_name" not in data:
            data["company_name"] = "This Company"
        if "company_summary" not in data:
            data["company_summary"] = "A growing organization"
        if "main_products" not in data:
            data["main_products"] = ["your solutions"]
        if "industry" not in data:
            data["industry"] = "your industry"
        if "ideal_audience" not in data:
            data["ideal_audience"] = ["Businesses needing scalable solutions"]
        if "ideal_customers" not in data:
            data["ideal_customers"] = ["Decision-makers in your industry"]
        return data
    except Exception:
        return None

# -------------------------
# Call AI for Insights
# -------------------------
def groq_ai_generate_insights(url: str, text: str) -> str:
    """
    Ask the model to return ONLY the JSON insights string in the specified structure.
    """
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""
Return output ONLY in this JSON format (no explanation, nothing else):

{{
  "company_name": "<company name>",
  "company_summary": "<short overview>",
  "main_products": ["product/service1", "product/service2"],
  "industry": "<recognized industry>",
  "ideal_audience": [
    "segment who benefits",
    "another audience segment"
  ],
  "ideal_customers": [
    "decision-maker role",
    "persona aligned to ICP"
  ]
}}

Company URL: {url}
Website Content: {text}
"""

    body = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.25
    }

    try:
        r = requests.post(API_URL, headers=headers, json=body, timeout=30)
        res = r.json()
        return res["choices"][0]["message"]["content"]
    except Exception:
        return ""

# -------------------------
# Generate Outreach Email
# -------------------------
def groq_ai_generate_email(url: str, text: str, tone: str, insights: dict) -> str:
    """
    Produce an email in one of two tones (professional / friendly).
    Uses fallback if insights missing. Applies smart_filter before returning.
    """
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    # Ensure insights exist; provide fallback defaults if not
    if not insights:
        insights = {
            "company_name": "This Company",
            "company_summary": "A growing organization",
            "main_products": ["your solutions"],
            "industry": "your industry",
            "ideal_audience": ["Businesses needing scalable solutions"],
            "ideal_customers": ["Decision-makers in your industry"]
        }

    company_name = insights.get("company_name", "This Company")
    main_products = ", ".join(insights.get("main_products", ["your solutions"]))
    industry = insights.get("industry", "your industry")
    ideal_customers_list = insights.get("ideal_customers", ["Decision-makers in your industry"])
    customers_bullets = "\n• ".join(ideal_customers_list)

    if "professional" in tone.lower():
        prompt = f"""
Return ONLY the email (no extra text). Use this exact structure:

Subject: Quick question about growth at {company_name}

Hello [First Name],

I noticed {company_name} is doing strong work in {industry}, especially around {main_products}. That momentum is a real advantage in your market.

To help accelerate outreach, we provide accurately profiled decision-makers aligned to your ICP. Here’s who you can connect with faster:

• {customers_bullets}

If helpful, I can share a quick preview dataset matched to your current targeting — no pressure.

Regards,
Ranjith
"""
    else:
        prompt = f"""
Return ONLY the email (no extra text). Use this exact structure:

Subject: A small idea for {company_name} 🚀

Hi [First Name],

Checked out {company_name} — love how you're pushing innovation in {industry}. The work you’re doing with {main_products} really stands out. 🙌

Thought a quick boost in your prospecting pipeline could help that momentum — we share decision-makers who match your ICP 👇

• {customers_bullets}

If it sounds useful, I’d be happy to send a short sample so you can judge the fit — totally pressure-free.

Cheers,
Ranjith 🚀
"""

    body = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5
    }

    try:
        r = requests.post(API_URL, headers=headers, json=body, timeout=30)
        res = r.json()
        email_text = res["choices"][0]["message"]["content"]
        # apply spam-safe replacements
        return smart_filter(email_text)
    except Exception:
        # fallback simple template if API fails
        fallback_email = f"""Subject: Quick question about growth at {company_name}

Hello [First Name],

I noticed {company_name} is doing strong work in {industry}. We provide decision-maker contacts such as:
• {customers_bullets}

Happy to share a short sample — no pressure.

Regards,
Ranjith
"""
        return smart_filter(fallback_email)

# -------------------------
# Parse Subject & Body
# -------------------------
def parse_email(content: str):
    subject = ""
    body = ""
    if not content:
        return subject, body
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.lower().startswith("subject:"):
            subject = line.split(":", 1)[1].strip()
            body = "\n".join(lines[i+1:]).strip()
            break
    # If subject not found, treat entire content as body
    if not subject:
        body = content.strip()
    return subject, body

# -------------------------
# Single URL Mode
# -------------------------
def analyze_single_url():
    url = st.text_input("Enter Website URL:")
    if st.button("Analyze"):
        if not url:
            st.error("Please enter a valid website URL.")
            return

        scraped = scrape_website(url)
        st.subheader("⏳ Processing...")

        # Get insights string and parse JSON
        insights_raw = groq_ai_generate_insights(url, scraped)
        insights = extract_json(insights_raw)

        # generate emails for both tones (uses fallback if insights is None)
        prof_email = groq_ai_generate_email(url, scraped, "professional", insights)
        friendly_email = groq_ai_generate_email(url, scraped, "friendly", insights)

        sp, bp = parse_email(prof_email)
        sf, bf = parse_email(friendly_email)

        st.subheader("📌 Company Insights")
        if insights:
            # show full insights JSON
            st.json(insights)
            # show ideal_audience in a friendly list
            if insights.get("ideal_audience"):
                st.markdown("### 🎯 Ideal Audience")
                for a in insights["ideal_audience"]:
                    st.write(f"- {a}")
        else:
            st.warning("Limited insights extracted — fallback values used.")
            st.json({
                "company_name": "This Company",
                "company_summary": "A growing organization",
                "main_products": ["your solutions"],
                "industry": "your industry",
                "ideal_audience": ["Businesses needing scalable solutions"],
                "ideal_customers": ["Decision-makers in your industry"]
            })

        st.subheader("1️⃣ Professional Corporate Tone")
        st.text_area("Professional Email", f"Subject: {sp}\n\n{bp}", height=250)

        st.subheader("2️⃣ Friendly Conversational Tone")
        st.text_area("Friendly Email", f"Subject: {sf}\n\n{bf}", height=250)

# -------------------------
# Bulk CSV Mode
# -------------------------
def analyze_bulk():
    file = st.file_uploader("Upload CSV with 'url' column", type=["csv"])
    if file is None:
        return

    try:
        df = pd.read_csv(file)
    except Exception:
        st.error("Unable to read CSV. Ensure it's a valid CSV file.")
        return

    if "url" not in df.columns:
        st.error("CSV must contain 'url' column")
        return

    if st.button("Run Bulk"):
        results = []
        progress = st.progress(0)
        total = len(df)
        for i, row in df.iterrows():
            url = row.get("url", "")
            scraped = scrape_website(url)

            insights_raw = groq_ai_generate_insights(url, scraped)
            insights = extract_json(insights_raw)

            p = groq_ai_generate_email(url, scraped, "professional", insights)
            f = groq_ai_generate_email(url, scraped, "friendly", insights)

            sp, bp = parse_email(p)
            sf, bf = parse_email(f)

            # Keep insights minimal in CSV: company_name + ideal_audience as joined string
            company_name = (insights.get("company_name") if insights else "This Company")
            ideal_audience_str = ", ".join(insights.get("ideal_audience", [])) if insights else ""

            results.append({
                "url": url,
                "company_name": company_name,
                "ideal_audience": ideal_audience_str,
                "professional_subject": sp,
                "professional_body": bp,
                "friendly_subject": sf,
                "friendly_body": bf,
            })

            progress.progress((i + 1) / total)

        out_df = pd.DataFrame(results)
        st.success("Bulk Email Generation Completed!")
        st.dataframe(out_df)

        st.download_button(
            "Download Results CSV",
            out_df.to_csv(index=False).encode("utf-8"),
            "email_results.csv",
            "text/csv"
        )

# -------------------------
# UI Layout
# -------------------------
st.title("🌐 Website Outreach AI Agent (Groq)")

mode = st.radio("Select Mode", ["Single URL", "Bulk CSV Upload"])
if mode == "Single URL":
    analyze_single_url()
else:
    analyze_bulk()
