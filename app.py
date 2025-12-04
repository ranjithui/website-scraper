import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import re

st.set_page_config(page_title="Website Outreach AI Agent", layout="wide")

# Load API key
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL_NAME = "llama-3.3-70b-versatile"

# ------------------------------------
# Smart Spam-Word Filter
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
}

def smart_filter(text):
    for pattern, replacement in spam_words_map.items():
        text = re.sub(pattern, replacement, text)
    return text

# ------------------------------------
# Website Scraper
# ------------------------------------
def scrape_website(url):
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        return text[:4000]
    except:
        return ""

# ------------------------------------
# JSON Extraction
# ------------------------------------
def extract_json(content):
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        json_str = content[start:end]
        data = json.loads(json_str)
        return data
    except:
        return None

# ------------------------------------
# AI Insights
# ------------------------------------
def groq_ai_generate_insights(url, text):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""
Extract ONLY JSON insights:

{{
"company_name": "Company Name",
"company_summary": "Short 2-3 line summary",
"main_products": ["service 1", "service 2"],
"ideal_customers": ["ICP1", "ICP2", "ICP3"],
"industry": "Industry guess"
}}

URL: {url}
Content: {text}
"""

    body = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }

    try:
        r = requests.post(API_URL, headers=headers, json=body)
        return r.json()["choices"][0]["message"]["content"]
    except:
        return ""

# ------------------------------------
# Email Generation With Fallbacks
# ------------------------------------
def groq_ai_generate_email(url, text, tone, insights):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    # Fallback if JSON missing / invalid
    if not insights:
        insights = {
            "company_name": "This Company",
            "company_summary": "A growing organization",
            "main_products": ["your solutions"],
            "ideal_customers": ["Decision-makers in your market"],
            "industry": "your industry"
        }

    company_name = insights["company_name"]
    company_summary = insights["company_summary"]
    main_products = ", ".join(insights["main_products"])
    industry = insights["industry"]
    customers_bullets = "\n• ".join(insights["ideal_customers"])

    if "professional" in tone.lower():
        prompt = f"""
Return ONLY the email:

Subject: Quick question about growth at {company_name}

Hello [First Name],

I noticed {company_name} is doing strong work in {industry}, especially around {main_products}. That momentum is a real advantage.

We provide accurately profiled decision-makers aligned to your ICP. Here’s who you can connect with faster:

• {customers_bullets}

If helpful, I can share a quick preview dataset — no pressure.

Regards,
Ranjith
"""
    else:
        prompt = f"""
Return ONLY the email:

Subject: A small idea for {company_name} 🚀

Hi [First Name],

Really impressed with {company_name} and your work in {industry}. What you're doing with {main_products} stands out. 🙌

We help teams boost outreach with decision-makers who match your ICP:

• {customers_bullets}

If you’d like, I can share a short sample so you can check relevance first.

Cheers,
Ranjith 🚀
"""

    body = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.55
    }

    try:
        res = requests.post(API_URL, headers=headers, json=body).json()
        email_text = res["choices"][0]["message"]["content"]
        return smart_filter(email_text)
    except:
        return ""

# ------------------------------------
# Parse Email
# ------------------------------------
def parse_email(content):
    subject, body = "", ""
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.lower().startswith("subject:"):
            subject = line.split(":", 1)[1].strip()
            body = "\n".join(lines[i+1:]).strip()
            break
    return subject, body

# ------------------------------------
# Single URL Mode
# ------------------------------------
def analyze_single_url():
    url = st.text_input("Enter Website URL:")

    if st.button("Analyze"):
        scraped = scrape_website(url)

        insights_raw = groq_ai_generate_insights(url, scraped)
        insights = extract_json(insights_raw)

        prof_email = groq_ai_generate_email(url, scraped, "professional", insights)
        friendly_email = groq_ai_generate_email(url, scraped, "friendly", insights)

        sp, bp = parse_email(prof_email)
        sf, bf = parse_email(friendly_email)

        st.subheader("📌 Company Insights")
        st.json(insights if insights else {"⚠️": "Limited insights extracted — fallback applied"})

        st.subheader("1️⃣ Professional Corporate Tone")
        st.text_area("Professional Email", f"Subject: {sp}\n\n{bp}", height=250)

        st.subheader("2️⃣ Friendly Conversational Tone")
        st.text_area("Friendly Email", f"Subject: {sf}\n\n{bf}", height=250)

# ------------------------------------
# Bulk Mode
# ------------------------------------
def analyze_bulk():
    file = st.file_uploader("Upload CSV with 'url' column", type=["csv"])
    if file is not None:
        df = pd.read_csv(file)
        if "url" not in df.columns:
            st.error("CSV must contain 'url' column")
            return

        if st.button("Run Bulk"):
            results = []
            progress = st.progress(0)

            for i, row in df.iterrows():
                url = row["url"]
                scraped = scrape_website(url)

                insights_raw = groq_ai_generate_insights(url, scraped)
                insights = extract_json(insights_raw)

                p = groq_ai_generate_email(url, scraped, "professional", insights)
                f = groq_ai_generate_email(url, scraped, "friendly", insights)

                sp, bp = parse_email(p)
                sf, bf = parse_email(f)

                results.append({
                    "url": url,
                    "professional_subject": sp,
                    "professional_body": bp,
                    "friendly_subject": sf,
                    "friendly_body": bf,
                })

                progress.progress((i+1)/len(df))

            st.success("Bulk Email Generation Completed!")
            st.dataframe(pd.DataFrame(results))


# ------------------------------------
# UI
# ------------------------------------
st.title("🌐 Website Outreach AI Agent (Groq)")
mode = st.radio("Select Mode", ["Single URL", "Bulk CSV Upload"])

if mode == "Single URL":
    analyze_single_url()
else:
    analyze_bulk()
