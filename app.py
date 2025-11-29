import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json

st.set_page_config(page_title="Website Outreach AI Agent", layout="wide")

# Load API key from Streamlit secrets
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]

API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL_NAME = "llama-3.3-70b-versatile"

# -------------------------
# Scrape website content
# -------------------------
def scrape_website(url):
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        texts = soup.get_text(separator=" ", strip=True)
        return texts[:4000]  # limit tokens
    except Exception as e:
        st.warning(f"Failed to scrape {url}: {e}")
        return ""

# -------------------------
# Call Groq AI API
# -------------------------
def groq_ai_analyze(url, text, style):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    if style == "Professional":
        prompt = f"""
You are a B2B sales outreach AI Agent.

Task: Analyze the company using the URL and scraped content below, and generate a **ready-to-send professional cold email** to sell our targeted B2B email lists.

Requirements for the email:

1. Email Subject: short, catchy, relevant.
2. Email Body:
   - Proper spacing between paragraphs
   - Include bullets for target audience
   - Highlight key phrases (like "**targeted email lists**", "**sample list**") in bold
   - Include ✅ emoji for call-to-action
   - 4–6 lines, copy-paste ready

Provide output in this structure:

1️⃣ Company Summary (2 lines)
2️⃣ Ideal Target Audience (3 bullet points)
3️⃣ Best Outreach Angles (2 bullet points)
4️⃣ Cold Email (ready-to-send, properly formatted):

📧 Email Subject:  
📨 Email Body:

Website: {url}

Scraped Content:  
{text}
"""
    else:  # Humble & Conversational Style
        prompt = f"""
You are a B2B sales outreach AI Agent.

Task: Analyze the company using the URL and scraped content below, and generate a **humble, conversational cold email** in ready-to-copy format.

Requirements:

1. Start with a friendly greeting in a humble tone
2. Include brief company info (2–3 lines)
3. Mention industry/field
4. Include target customers relevant to the company in bullets
5. Highlight key phrases (like "**targeted B2B email lists**", "**sample list**") in bold
6. Include ✅ emoji for the call-to-action
7. Proper spacing between paragraphs
8. 4–6 lines in the email body
9. End with a polite, engaging line (like "Looking forward to your thoughts!")

Provide output in this structure:

📧 Email Subject:  
📨 Email Body:

Website: {url}

Scraped Content:  
{text}
"""

    body = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }

    try:
        r = requests.post(API_URL, headers=headers, json=body)
        response = r.json()

        if "choices" not in response:
            return f"❌ Groq API Unexpected Response: {json.dumps(response, indent=2)}"

        content = response["choices"][0]["message"]["content"]
        return content

    except Exception as e:
        return f"⚠️ API Error: {e}"

# -------------------------
# Parse AI output
# -------------------------
def parse_analysis(content):
    email_subject = ""
    email_body = ""
    try:
        lines = content.splitlines()
        buffer = []
        mode = None
        for line in lines:
            line_strip = line.strip()
            if "📧 Email Subject:" in line_strip:
                email_subject = line_strip.replace("📧 Email Subject:", "").strip()
                mode = "email_body"
                buffer = []
            elif "📨 Email Body:" in line_strip:
                mode = "email_body"
                buffer = []
            elif mode == "email_body":
                buffer.append(line_strip)
        email_body = "\n".join(buffer)
    except Exception as e:
        st.warning(f"Parsing error: {e}")
    return email_subject, email_body

# -------------------------
# Display both email versions
# -------------------------
def analyze_single_url():
    url = st.text_input("Enter Website URL:")
    if st.button("Analyze"):
        if url:
            text = scrape_website(url)

            st.subheader("📌 Generating Emails... Please wait.")

            # Professional Email
            content_prof = groq_ai_analyze(url, text, "Professional")
            subject_prof, body_prof = parse_analysis(content_prof)

            # Humble & Conversational Email
            content_humble = groq_ai_analyze(url, text, "Humble & Conversational")
            subject_humble, body_humble = parse_analysis(content_humble)

            st.subheader("1️⃣ Professional Email")
            st.text_area("Copy & Paste Ready Email", f"📧 Email Subject:\n{subject_prof}\n\n📨 Email Body:\n{body_prof}", height=250)

            st.subheader("2️⃣ Humble & Conversational Email")
            st.text_area("Copy & Paste Ready Email", f"📧 Email Subject:\n{subject_humble}\n\n📨 Email Body:\n{body_humble}", height=250)

# -------------------------
# Bulk CSV Analysis
# -------------------------
def analyze_bulk():
    file = st.file_uploader("Upload CSV with 'url' column", type=["csv"])
    if file is not None:
        df = pd.read_csv(file)
        if "url" not in df.columns:
            st.error("CSV must contain a 'url' column")
            return

        if st.button("Run Bulk Analysis"):
            results = []
            progress = st.progress(0)

            for i, row in df.iterrows():
                url = row["url"]
                text = scrape_website(url)

                # Professional Email
                content_prof = groq_ai_analyze(url, text, "Professional")
                subject_prof, body_prof = parse_analysis(content_prof)

                # Humble & Conversational Email
                content_humble = groq_ai_analyze(url, text, "Humble & Conversational")
                subject_humble, body_humble = parse_analysis(content_humble)

                results.append({
                    "url": url,
                    "professional_subject": subject_prof,
                    "professional_body": body_prof,
                    "humble_subject": subject_humble,
                    "humble_body": body_humble
                })

                progress.progress((i + 1) / len(df))

            result_df = pd.DataFrame(results)
            st.success("Bulk Analysis Completed!")
            st.dataframe(result_df)

            csv = result_df.to_csv(index=False).encode('utf-8')
            st.download_button("Download Results CSV", csv, "results.csv", "text/csv")

# -------------------------
# UI Layout
# -------------------------
st.title("🌐 Website Outreach AI Agent (Groq)")

mode = st.radio("Select Mode", ["Single URL", "Bulk CSV Upload"])

if mode == "Single URL":
    analyze_single_url()
else:
    analyze_bulk()
