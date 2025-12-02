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
        return json.loads(json_str)
    except:
        return None


# -------------------------
# Groq AI Email Generator
# -------------------------
def groq_ai_generate(url, text, tone, company_summary):

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""
You are a B2B sales outreach expert.

Analyze the company details below and generate:

1️⃣ JSON Insights:
{{
"company_summary": "2-3 line summary",
"main_products": ["service 1", "service 2", "service 3"],
"ideal_customers": ["ICP1", "ICP2", "ICP3"],
"industry": "best guess industry"
}}

2️⃣ Email outreach ONLY in TWO tones using EXACT format below.

---

📌 Professional Corporate Tone  
Subject: Enhance Your Outreach with Targeted Contacts at [Company Name]

Hello [First Name],

I noticed [Company Name] is focusing on [specific product/service/market focus].  
We provide targeted email lists to help you connect with:
• CIOs
• Product Managers
• Risk Officers

If this aligns with your outreach strategy, I’d be happy to share more details along with a small sample for your review.

Looking forward to your thoughts,  
Ranjith

---

📌 Friendly Conversational Tone  
Subject: Connect with Key Decision-Makers at [Company Name]

Hi [First Name],  

I came across [Company Name] and noticed you’re doing exciting work in [industry/product/project focus].  
We provide targeted email lists to help you reach:
• Marketing Managers
• Operations Leads
• Tech Team Heads

If you're open to it, I’d love to share more details — plus a small sample list so you can see the fit firsthand.

What do you say — should we give it a quick try? 😊  

Cheers,  
Ranjith 🚀  

---

⚠️ Additional rules:
- Do NOT mention scraping
- Keep email short
- Replace placeholders contextually based on industry
- Keep structure same (don't add/remove sections)

Company URL: {url}
Company Summary: {company_summary}
Scraped Content: {text}
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
    except Exception as e:
        return f"⚠️ API Error: {e}"


# -------------------------
# Parse Subject + Email
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

            base_resp = groq_ai_generate(url, scraped, "Professional Corporate Tone", "Analyzing...")
            insights = extract_json(base_resp)

            company_summary = insights["company_summary"] if insights else "A growing organization"

            prof = groq_ai_generate(url, scraped, "Professional Corporate Tone", company_summary)
            conv = groq_ai_generate(url, scraped, "Friendly Conversational Tone", company_summary)
            consult = groq_ai_generate(url, scraped, "Insight-Driven Consultative Tone", company_summary)
            urgent = groq_ai_generate(url, scraped, "Urgency Action-Oriented Tone", company_summary)

            sp, bp = parse_email(prof)
            sc, bc = parse_email(conv)
            si_sub, si_body = parse_email(consult)
            sa_sub, sa_body = parse_email(urgent)

            st.subheader("📌 Company Insights")
            st.json(insights)

            st.subheader("1️⃣ Professional Corporate Tone")
            st.text_area("Professional", f"Subject: {sp}\n\n{bp}", height=260)

            st.subheader("2️⃣ Friendly Conversational Tone")
            st.text_area("Conversational", f"Subject: {sc}\n\n{bc}", height=260)

            st.subheader("3️⃣ Insight-Driven Consultative Tone")
            st.text_area("Insight-Driven", f"Subject: {si_sub}\n\n{si_body}", height=260)

            st.subheader("4️⃣ Action-Oriented Urgency Tone")
            st.text_area("Action-Oriented", f"Subject: {sa_sub}\n\n{sa_body}", height=260)


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

                base_resp = groq_ai_generate(url, scraped, "Professional Corporate Tone", "Analyzing...")
                insights = extract_json(base_resp)
                company_summary = insights["company_summary"] if insights else "A growing organization"

                prof = groq_ai_generate(url, scraped, "Professional Corporate Tone", company_summary)
                conv = groq_ai_generate(url, scraped, "Friendly Conversational Tone", company_summary)
                consult = groq_ai_generate(url, scraped, "Insight-Driven Consultative Tone", company_summary)
                urgent = groq_ai_generate(url, scraped, "Urgency Action-Oriented Tone", company_summary)

                sp, bp = parse_email(prof)
                sc, bc = parse_email(conv)
                si_sub, si_body = parse_email(consult)
                sa_sub, sa_body = parse_email(urgent)

                results.append({
                    "url": url,
                    "professional_subject": sp,
                    "professional_body": bp,
                    "conversational_subject": sc,
                    "conversational_body": bc,
                    "insight_subject": si_sub,
                    "insight_body": si_body,
                    "action_subject": sa_sub,
                    "action_body": sa_body
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
