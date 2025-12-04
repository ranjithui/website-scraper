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
# Call AI for Insights
# -------------------------
def groq_ai_generate_insights(url, text):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""
You are a business analyst. Extract ONLY JSON insights from the website.

Return in this exact JSON format:

{{
"company_name": "Company Name",
"company_summary": "2-3 line summary",
"main_products": ["service 1", "service 2", "service 3"],
"ideal_customers": ["ICP1", "ICP2", "ICP3"],
"industry": "best guess industry"
}}

Company URL: {url}
Website Content: {text}
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
# Smart Spam-Word Cleaner
# -------------------------
def clean_spam_words(text):
    replacements = {
        r"\bfree\b": "complimentary",
        r"\bbuy\b": "consider",
        r"\bguaranteed\b": "confident",
        r"\bbest price\b": "optimized pricing",
        r"\boffer\b": "solution",
        r"\bsale\b": "rollout",
        r"\blimited time\b": "prioritized timeline",
        r"\bact now\b": "let me know if helpful",
        r"\bhurry\b": "let me know if helpful",
        r"\bexclusive access\b": "early access",
        r"\bearn\b": "achieve",
        r"\bprofit\b": "business growth",
        r"\brisk-free\b": "optional",
        r"\bamazing\b": "meaningful",
        r"\bmoney\b": "budget",
        r"\bcredit\b": "approval"
    }
    for bad, good in replacements.items():
        text = re.sub(bad, good, text, flags=re.IGNORECASE)
    return text

# -------------------------
# Spam Score Calculator
# -------------------------
def calculate_spam_score(text):
    spam_keywords = [
        "free", "buy", "guaranteed", "best price", "offer", "sale",
        "limited time", "act now", "hurry", "exclusive access",
        "earn", "profit", "risk-free", "money", "credit"
    ]
    text_lower = text.lower()
    risk_count = sum(1 for keyword in spam_keywords if keyword in text_lower)
    score = max(0, 100 - (risk_count * 10))
    if score >= 85:
        status = "🟢 Excellent Deliverability"
    elif score >= 70:
        status = "🟡 Good But Can Improve"
    else:
        status = "🔴 High Risk — Needs Fixing"
    return score, status

# -------------------------
# Generate Outreach Email
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
    customers_bullets = "\n• ".join(ideal_customers) if ideal_customers else "your target audience"

    if "professional" in tone.lower():
        prompt = f"""
Subject: Enhance Your Outreach with Targeted Contacts at {company_name}

Hello [First Name],

I noticed {company_name} is focusing on {main_products}.
We provide targeted email lists to help you connect with:
• {customers_bullets}

If this aligns with your outreach strategy, I’d be happy to share more details with a small sample for review.

Looking forward to your thoughts,
Ranjith
"""
    else:
        prompt = f"""
Subject: Connect with Key Decision-Makers at {company_name}

Hi [First Name],

I came across {company_name} and noticed you're doing great work in {industry}.
We provide targeted email lists to help you reach:
• {customers_bullets}

If you're open to it, I'd love to share a quick sample so you can validate the fit.

Cheers,
Ranjith 🚀
"""

    try:
        body = {
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.55
        }
        r = requests.post(API_URL, headers=headers, json=body)
        return r.json()["choices"][0]["message"]["content"]
    except Exception:
        return ""

# -------------------------
# Extract Subject & Body
# -------------------------
def parse_email(content):
    subject, body = "", ""
    lines = content.splitlines()
    for i, l in enumerate(lines):
        if l.lower().startswith("subject:"):
            subject = l.split(":", 1)[1].strip()
            body = "\n".join(lines[i+1:]).strip()
            break
    return subject, body

# -------------------------
# Single URL Output
# -------------------------
def analyze_single_url():
    url = st.text_input("Enter Website URL:")
    if st.button("Analyze") and url:
        scraped = scrape_website(url)
        st.subheader("⏳ Processing... Please wait...")

        insights_raw = groq_ai_generate_insights(url, scraped)
        insights = extract_json(insights_raw)

        prof_email = groq_ai_generate_email(url, scraped, "professional", insights)
        friendly_email = groq_ai_generate_email(url, scraped, "friendly", insights)

        sp, bp = parse_email(prof_email)
        sf, bf = parse_email(friendly_email)

        # Clean
        sp, bp = clean_spam_words(sp), clean_spam_words(bp)
        sf, bf = clean_spam_words(sf), clean_spam_words(bf)

        score_p, status_p = calculate_spam_score(sp + " " + bp)
        score_f, status_f = calculate_spam_score(sf + " " + bf)

        st.json(insights)
        st.subheader("1️⃣ Professional Tone")
        st.markdown(f"**Spam Score:** {score_p}/100 — {status_p}")
        st.text_area("Professional Email", f"Subject: {sp}\n\n{bp}", height=220)

        st.subheader("2️⃣ Friendly Tone")
        st.markdown(f"**Spam Score:** {score_f}/100 — {status_f}")
        st.text_area("Friendly Email", f"Subject: {sf}\n\n{bf}", height=220)

# -------------------------
# Bulk CSV Upload
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

                p = groq_ai_generate_email(url, scraped, "professional", insights)
                f = groq_ai_generate_email(url, scraped, "friendly", insights)

                sp, bp = parse_email(p)
                sf, bf = parse_email(f)

                sp, bp = clean_spam_words(sp), clean_spam_words(bp)
                sf, bf = clean_spam_words(sf), clean_spam_words(bf)

                score_p, _ = calculate_spam_score(sp + " " + bp)
                score_f, _ = calculate_spam_score(sf + " " + bf)

                results.append({
                    "url": url,
                    "professional_subject": sp,
                    "professional_body": bp,
                    "professional_spam_score": score_p,
                    "friendly_subject": sf,
                    "friendly_body": bf,
                    "friendly_spam_score": score_f
                })

                progress.progress((i+1) / len(df))

            out_df = pd.DataFrame(results)
            st.success("Completed!")
            st.dataframe(out_df)

            st.download_button(
                "Download CSV",
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
