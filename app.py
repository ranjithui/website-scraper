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
# Extract Hook Words
# -------------------------
def extract_hook_words(text):
    # Take first 2-3 sentences or key phrases from website
    sentences = re.split(r'\. |\n', text)
    hooks = []
    for s in sentences:
        if len(s) > 20 and len(hooks) < 2:
            hooks.append(s.strip())
    return " ".join(hooks) if hooks else "innovative solutions in their industry"

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
# Groq AI Generator
# -------------------------
def groq_ai_generate(url, text, style, company_summary, hooks):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""
You are a B2B email expert.

Company Info:
URL: {url}
Summary: {company_summary}
Hook Words: {hooks}

Generate an email in the following style: {style}

Email Format:
Subject: One-line sales subject

Hello [First Name],

We offer targeted email lists to help you connect with:
• {{ICP1}}
• {{ICP2}}
• {{ICP3}}

If this could help your outreach efforts, I’d be happy to share more details along with a small sample for your review.
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
# Single URL Mode
# -------------------------
def analyze_single_url():
    url = st.text_input("Enter Website URL:")

    if st.button("Analyze"):
        if url:
            scraped = scrape_website(url)
            hooks = extract_hook_words(scraped)
            st.subheader("⏳ Processing... Please wait")

            # Generate JSON + Insight Summary
            base = groq_ai_generate(url, scraped, "Professional Corporate Tone", "Analyzing...", hooks)
            insights = extract_json(base)
            company_summary = insights["company_summary"] if insights else "A growing organization"

            # Generate 2 Tone Versions
            prof = groq_ai_generate(url, scraped, "Professional Corporate Tone", company_summary, hooks)
            conv = groq_ai_generate(url, scraped, "Friendly Conversational Tone", company_summary, hooks)

            sp, bp = parse_email(prof)
            sc, bc = parse_email(conv)

            st.subheader("📌 Company Insights")
            st.json(insights)

            st.subheader("1️⃣ Professional Corporate Tone")
            st.text_area("Professional", f"Subject: {sp}\n\n{bp}", height=260)

            st.subheader("2️⃣ Friendly Conversational Tone")
            st.text_area("Conversational", f"Subject: {sc}\n\n{bc}", height=260)

# -------------------------
# Bulk CSV Upload Mode
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
                hooks = extract_hook_words(scraped)

                base = groq_ai_generate(url, scraped, "Professional Corporate Tone", "Analyzing...", hooks)
                insights = extract_json(base)
                company_summary = insights["company_summary"] if insights else "A growing organization"

                prof = groq_ai_generate(url, scraped, "Professional Corporate Tone", company_summary, hooks)
                conv = groq_ai_generate(url, scraped, "Friendly Conversational Tone", company_summary, hooks)

                sp, bp = parse_email(prof)
                sc, bc = parse_email(conv)

                results.append({
                    "url": url,
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

mode = st.radio("Select Mode", ["Single URL", "Bulk CSV Upload"])

if mode == "Single URL":
    analyze_single_url()
else:
    analyze_bulk()
