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
# Smart Spam-Word Filter & Replacements
# ------------------------------------
spam_words_map = {
    r"(?i)\bbuy\b": "explore",
    r"(?i)\bbulk\b": "large-scale",
    r"(?i)\bemail list\b": "decision-maker contacts",
    r"(?i)\bguarantee\b": "support",
    r"(?i)\bcheap\b": "budget-friendly",
    r"(?i)\bfree leads\b": "sample contacts",
    r"(?i)\bpurchase\b": "access",
    r"(?i)\bno risk\b": "no pressure",
    r"(?i)\bspecial offer\b": "exclusive support",
}

def smart_filter(text):
    for pattern, replacement in spam_words_map.items():
        text = re.sub(pattern, replacement, text)
    return text


# -------------------------
# Scrape Website Content
# -------------------------
def scrape_website(url):
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        return text[:4000]
    except Exception as e:
        st.warning(f"Failed to scrape {url}: {e}")
        return ""


# -------------------------
# Extract JSON Insights
# -------------------------
def extract_json(content):
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        json_str = content[start:end]
        data = json.loads(json_str)
        if "company_name" not in data:
            data["company_name"] = "This Company"
        if "ideal_customers" not in data:
            data["ideal_customers"] = []
        return data
    except:
        return None


# -------------------------
# Call AI for Insights Only
# -------------------------
def groq_ai_generate_insights(url, text):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""
Extract ONLY JSON insights. Strict format:

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
        res = r.json()
        return res["choices"][0]["message"]["content"]
    except Exception:
        return ""


# -------------------------
# AI Email Generator
# -------------------------
def groq_ai_generate_email(url, text, tone, insights):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    company_name = insights.get("company_name", "This Company")
    company_summary = insights.get("company_summary", "A growing organization")
    main_products = ", ".join(insights.get("main_products", []))
    industry = insights.get("industry", "your industry")
    ideal_customers = insights.get("ideal_customers", [])
    customers_bullets = "\n• ".join(ideal_customers) if ideal_customers else "• Target decision-makers in your market"

    if "professional" in tone.lower():
        prompt = f"""
Return ONLY email in EXACT format:

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
Return ONLY email in EXACT format:

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
        "temperature": 0.55
    }

    try:
        r = requests.post(API_URL, headers=headers, json=body)
        res = r.json()
        email_text = res["choices"][0]["message"]["content"]
        return smart_filter(email_text)
    except Exception:
        return ""


# -------------------------
# Parse Email Output
# -------------------------
def parse_email(content):
    subject = ""
    body = ""
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.lower().startswith("subject:"):
            subject = line.split(":", 1)[1].strip()
            body = "\n".join(lines[i+1:]).strip()
            break
    return subject, body


# -------------------------
# Single URL Mode
# -------------------------
def analyze_single_url():
    url = st.text_input("Enter Website URL:")

    if st.button("Analyze"):
        if url:
            scraped = scrape_website(url)
            st.subheader("⏳ Processing... Please wait")

            insights_raw = groq_ai_generate_insights(url, scraped)
            insights = extract_json(insights_raw)

            prof_email = groq_ai_generate_email(url, scraped, "Professional", insights)
            friendly_email = groq_ai_generate_email(url, scraped, "Friendly", insights)

            sp, bp = parse_email(prof_email)
            sf, bf_body = parse_email(friendly_email)

            st.subheader("📌 Company Insights")
            st.json(insights if insights else {"message": "No insights"})

            st.subheader("1️⃣ Professional Corporate Tone")
            st.text_area("Professional", f"Subject: {sp}\n\n{bp}", height=220)

            st.subheader("2️⃣ Friendly Conversational Tone")
            st.text_area("Friendly", f"Subject: {sf}\n\n{bf_body}", height=220)


# -------------------------
# Bulk CSV Mode
# -------------------------
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

                p = groq_ai_generate_email(url, scraped, "Professional", insights)
                f = groq_ai_generate_email(url, scraped, "Friendly", insights)

                sp, bp = parse_email(p)
                sf, bf_body = parse_email(f)

                results.append({
                    "url": url,
                    "professional_subject": sp,
                    "professional_body": bp,
                    "friendly_subject": sf,
                    "friendly_body": bf_body
                })

                progress.progress((i+1)/len(df))

            result_df = pd.DataFrame(results)

            st.success("Bulk Email Generation Completed!")
            st.dataframe(result_df)

            st.download_button(
                "Download Results CSV",
                result_df.to_csv(index=False).encode("utf-8"),
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
