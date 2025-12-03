import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json

st.set_page_config(page_title="Website Outreach AI Agent", layout="wide")

# Load API key
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL_NAME = "llama-3.3-70b-versatile"

# -----------------------------------------------------
# Smart Deliverability Filter (New)
# -----------------------------------------------------
def smart_filter_email(text):
    risky_phrases = [
        "100% verified", "100% guarantee", "guaranteed", "free",
        "free sample", "cheap", "act fast", "buy now",
        "unlimited leads", "no risk", "exclusive deal"
    ]

    for phrase in risky_phrases:
        text = text.replace(phrase, "")

    replacements = {
        "email lists": "targeted contact data",
        "high-quality leads": "relevant decision-makers",
        "grow fast": "support your outreach goals",
        "amazing results": "practical outcomes",
        "free trial": "a small trial dataset"
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # Remove excessive emojis
    emojis = "🚀🔥💥✨⚡"
    emoji_count = 0
    cleaned = ""
    for char in text:
        if char in emojis:
            if emoji_count < 1:
                emoji_count += 1
                cleaned += char
        else:
            cleaned += char

    return cleaned.strip()

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
You are a business analyst. Extract ONLY JSON insights from the website.

Return in this exact JSON format:

{{
"company_name": "Company Name",
"company_summary": "2-3 line summary",
"main_products": ["service 1", "service 2"],
"ideal_customers": ["ICP1", "ICP2"],
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
    except:
        return ""

# -------------------------
# Call AI for Emails with Spam-Free Prompts (New)
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
    customers_bullets = "\n• ".join(ideal_customers) if ideal_customers else "relevant decision-makers"

    if "professional" in tone.lower():
        prompt = f"""
You are a B2B sales outreach expert.

Craft a concise outreach email. Avoid spam-trigger words like “free”, “guarantee”, etc.
Be value-focused and professional.

Return ONLY this format:

Subject: Connect with the Right Decision-Makers at {company_name}

Hello [First Name],

I noticed {company_name} is focused on {main_products}.  
We help teams connect with the right decision-makers in {industry}, reducing time spent on unqualified outreach.

If you're open to it, I can share a small tailored sample for quick evaluation.

Warm regards,  
Ranjith
"""
    else:
        prompt = f"""
You are a B2B sales outreach expert.

Write a friendly, short outreach email without spam triggers.
Be casual but still business-relevant.

Return ONLY this format:

Subject: Quick Question About Outreach at {company_name}

Hi [First Name],  

Loved seeing how {company_name} is making an impact in {industry}.  
We help teams reach relevant decision-makers so outreach becomes more productive.

If it makes sense to explore, I can share a small example to check fit.

Thanks a ton,  
Ranjith
"""

    body = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.55
    }

    try:
        r = requests.post(API_URL, headers=headers, json=body)
        res = r.json()
        return res["choices"][0]["message"]["content"]
    except:
        return ""

# -------------------------
# Parse + Filter Emails (Updated)
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

    subject = smart_filter_email(subject)
    body = smart_filter_email(body)

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

            p = groq_ai_generate_email(url, scraped, "Professional Corporate Tone", insights)
            f = groq_ai_generate_email(url, scraped, "Friendly Conversational Tone", insights)

            sp, bp = parse_email(p)
            sf, bf = parse_email(f)

            st.subheader("📌 Company Insights")
            if insights:
                st.json(insights)
            else:
                st.text("No insights found")

            st.subheader("1️⃣ Professional Corporate Tone")
            st.text_area("Professional", f"Subject: {sp}\n\n{bp}", height=220)

            st.subheader("2️⃣ Friendly Conversational Tone")
            st.text_area("Friendly", f"Subject: {sf}\n\n{bf}", height=220)

# -------------------------
# Bulk Upload Mode
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
                summary = insights["company_summary"] if insights else "A growing organization"

                p = groq_ai_generate_email(url, scraped, "Professional Corporate Tone", insights)
                f = groq_ai_generate_email(url, scraped, "Friendly Conversational Tone", insights)

                sp, bp = parse_email(p)
                sf, bf = parse_email(f)

                results.append({
                    "url": url,
                    "company_summary": summary,
                    "professional_subject": sp,
                    "professional_body": bp,
                    "friendly_subject": sf,
                    "friendly_body": bf
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
st.title("🌐 Website Outreach AI Agent (Groq) — Spam Free Edition")

mode = st.radio("Select Mode", ["Single URL", "Bulk CSV Upload"])

if mode == "Single URL":
    analyze_single_url()
else:
    analyze_bulk()
