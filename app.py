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
def scrape_website(website):
    try:
        r = requests.get(website, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        return text[:4000]
    except Exception as e:
        st.warning(f"Failed to scrape {website}: {e}")
        return ""

# -------------------------
# Extract Hook Words
# -------------------------
def extract_hook_words(text):
    sentences = re.split(r'\. |\n', text)
    hooks = []
    for s in sentences:
        if len(s) > 20 and len(hooks) < 1:
            hooks.append(s.strip())
    return hooks[0] if hooks else "innovative solutions in their industry"

# -------------------------
# Generate JSON Insights
# -------------------------
def generate_json_insights(website, text):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""
You are a B2B data analyst. Based on the company website content below, extract the following in JSON:

1️⃣ company_summary: 1-2 sentence summary  
2️⃣ main_products: List main products/services  
3️⃣ target_roles: List 3 key decision-maker roles likely to use your product/service  
4️⃣ industry: Best guess industry

Website Content: {text}
Company URL: {website}
"""

    body = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }

    try:
        r = requests.post(API_URL, headers=headers, json=body)
        res = r.json()
        content = res["choices"][0]["message"]["content"]
        start = content.find("{")
        end = content.rfind("}") + 1
        return json.loads(content[start:end])
    except Exception as e:
        st.warning(f"JSON extraction failed: {e}")
        return None

# -------------------------
# Generate Short Email
# -------------------------
def generate_email(website, company_info, hooks, style):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""
You are a B2B email expert. Generate a **short email** in {style} using the following company info and hook.

Company Info:
{json.dumps(company_info)}

Hook: {hooks}

Email Format:
Subject: One-line sales subject

Hello [First Name],

We provide targeted email lists to connect with:
• {company_info['target_roles'][0]}
• {company_info['target_roles'][1]}
• {company_info['target_roles'][2]}

If this could help your outreach efforts, I’d be happy to share a small sample for your review.
"""

    body = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.55 if style=="Professional Corporate Tone" else 0.65
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
# Single Website Mode
# -------------------------
def analyze_single_website():
    website = st.text_input("Enter Website URL:")
    if st.button("Analyze"):
        if website:
            scraped = scrape_website(website)
            hooks = extract_hook_words(scraped)
            st.subheader("⏳ Processing... Please wait")

            company_info = generate_json_insights(website, scraped)
            if not company_info:
                company_info = {
                    "company_summary": "A growing organization",
                    "main_products": ["Product 1", "Product 2"],
                    "target_roles": ["Role 1", "Role 2", "Role 3"],
                    "industry": "Industry"
                }

            # Generate 2 Tone Emails (short)
            prof_email = generate_email(website, company_info, hooks, "Professional Corporate Tone")
            conv_email = generate_email(website, company_info, hooks, "Friendly Conversational Tone")

            sp, bp = parse_email(prof_email)
            sc, bc = parse_email(conv_email)

            st.subheader("📌 Company Insights")
            st.json(company_info)

            st.subheader("1️⃣ Professional Corporate Tone")
            st.text_area("Professional", f"Subject: {sp}\n\n{bp}", height=220)

            st.subheader("2️⃣ Friendly Conversational Tone")
            st.text_area("Conversational", f"Subject: {sc}\n\n{bc}", height=220)

# -------------------------
# Bulk CSV Upload Mode
# -------------------------
def analyze_bulk():
    file = st.file_uploader("Upload CSV with 'Website' column", type=["csv"])
    if file is not None:
        df = pd.read_csv(file)
        if "Website" not in df.columns:
            st.error("CSV must contain 'Website' column")
            return

        if st.button("Run Bulk"):
            results = []
            progress = st.progress(0)

            for i, row in df.iterrows():
                website = row["Website"]
                scraped = scrape_website(website)
                hooks = extract_hook_words(scraped)

                company_info = generate_json_insights(website, scraped)
                if not company_info:
                    company_info = {
                        "company_summary": "A growing organization",
                        "main_products": ["Product 1", "Product 2"],
                        "target_roles": ["Role 1", "Role 2", "Role 3"],
                        "industry": "Industry"
                    }

                prof_email = generate_email(website, company_info, hooks, "Professional Corporate Tone")
                conv_email = generate_email(website, company_info, hooks, "Friendly Conversational Tone")

                sp, bp = parse_email(prof_email)
                sc, bc = parse_email(conv_email)

                results.append({
                    "Website": website,
                    "professional_subject": sp,
                    "professional_body": bp,
                    "conversational_subject": sc,
                    "conversational_body": bc
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
# App UI Layout
# -------------------------
st.title("🌐 Website Outreach AI Agent (Groq)")

mode = st.radio("Select Mode", ["Single Website", "Bulk CSV Upload"])
if mode == "Single Website":
    analyze_single_website()
else:
    analyze_bulk()
