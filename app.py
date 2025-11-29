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
def groq_ai_analyze(url, text):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""
You are a B2B sales outreach AI Agent.

Task: Analyze the company from the URL and scraped content below and generate a **ready-to-send professional cold email** to sell our targeted B2B email lists.

Requirements:

1. Email Subject: short, catchy, relevant.
2. Email Body:
   - Use proper spacing between paragraphs.
   - Include bullets for target audience.
   - Highlight key phrases (like "**targeted email lists**", "**sample list**") using bold.
   - Include ✅ emoji for call-to-action.
   - 4-6 lines, copy-paste ready.

Provide output in this exact structure:

1️⃣ Company Summary (2 lines)

2️⃣ Ideal Target Audience (3 bullet points)

3️⃣ Best Outreach Angles (2 bullet points)

4️⃣ Cold Email (ready-to-send, properly formatted):

📧 Email Subject:  
📨 Email Body:

**Format Example:**

📧 Email Subject: Connect with Key Site Managers

📨 Email Body:
Hello,

We offer **targeted email lists** to help you connect with:  
- Mining operators and site managers  
- Fleet and transport managers  
- Safety and compliance officers  

Perfect if you offer services like **compliance, fleet performance, or site support**.  

✅ Let me know if you'd like a **sample**.

Website: {url}

Scraped Content:  
{text}
"""

    body = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "user", "content": prompt}
        ],
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
    company_summary = ""
    ideal_targets = ""
    outreach_angles = ""
    email_subject = ""
    email_body = ""

    try:
        lines = content.splitlines()
        mode = None
        buffer = []

        for line in lines:
            line_strip = line.strip()
            if "1️⃣" in line_strip:
                if buffer and mode:
                    if mode == "company_summary":
                        company_summary = " ".join(buffer)
                    buffer = []
                mode = "company_summary"
            elif "2️⃣" in line_strip:
                if buffer and mode:
                    if mode == "company_summary":
                        company_summary = " ".join(buffer)
                    elif mode == "ideal_targets":
                        ideal_targets = "\n".join(buffer)
                    buffer = []
                mode = "ideal_targets"
            elif "3️⃣" in line_strip:
                if buffer and mode:
                    if mode == "ideal_targets":
                        ideal_targets = "\n".join(buffer)
                    elif mode == "outreach_angles":
                        outreach_angles = "\n".join(buffer)
                    buffer = []
                mode = "outreach_angles"
            elif "📧 Email Subject:" in line_strip:
                if buffer and mode == "outreach_angles":
                    outreach_angles = "\n".join(buffer)
                mode = "email"
                email_subject = line_strip.replace("📧 Email Subject:", "").strip()
            elif "📨 Email Body:" in line_strip:
                mode = "email_body"
                buffer = []
            else:
                if mode in ["company_summary", "ideal_targets", "outreach_angles", "email_body"]:
                    buffer.append(line_strip)

        if buffer and mode == "email_body":
            email_body = "\n".join(buffer)

    except Exception as e:
        st.warning(f"Parsing error: {e}")

    return company_summary, ideal_targets, outreach_angles, email_subject, email_body

# -------------------------
# Single URL analysis
# -------------------------
def analyze_single_url():
    url = st.text_input("Enter Website URL:")
    if st.button("Analyze"):
        if url:
            text = scrape_website(url)
            content = groq_ai_analyze(url, text)
            st.subheader("Analysis Result")
            st.text_area("Raw AI Output", content, height=400)

            summary, targets, angles, subject, body = parse_analysis(content)

            st.subheader("📧 Ready-to-send Email")
            st.text_area("Copy & Paste Ready Email", f"📧 Email Subject:\n{subject}\n\n📨 Email Body:\n{body}", height=250)

# -------------------------
# Bulk CSV analysis
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
                content = groq_ai_analyze(url, text)
                summary, targets, angles, subject, body = parse_analysis(content)
                results.append({
                    "url": url,
                    "company_summary": summary,
                    "ideal_targets": targets,
                    "outreach_angles": angles,
                    "email_subject": subject,
                    "cold_email_body": body
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
