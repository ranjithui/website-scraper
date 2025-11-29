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

Task: Analyze the company using the URL and scraped content below, and generate a **ready-to-copy professional analysis and two cold email versions**.

Requirements:

1️⃣ Company Summary (2–3 lines)  
2️⃣ Industry/Field  
3️⃣ Ideal Target Audience (3 bullet points)  
4️⃣ Best Outreach Angles (2 bullet points)  

5️⃣ Cold Emails
   - Professional Email (copy-paste-ready, bullets, highlights, emoji ✅, 4–6 lines)  
   - Humble & Conversational Email (friendly tone, company info, industry, bullets, highlights, emoji ✅, 4–6 lines)

Format exactly like this:

1️⃣ Company Summary:  
2️⃣ Industry/Field:  
3️⃣ Ideal Target Audience:  
- Bullet 1  
- Bullet 2  
- Bullet 3  

4️⃣ Best Outreach Angles:  
- Bullet 1  
- Bullet 2  

5️⃣ Cold Emails:  
📧 Professional Email Subject:  
📨 Professional Email Body:  

📧 Humble & Conversational Email Subject:  
📨 Humble & Conversational Email Body:  

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
    # Initialize
    company_summary = ""
    industry = ""
    ideal_targets = ""
    outreach_angles = ""
    prof_subject = ""
    prof_body = ""
    humble_subject = ""
    humble_body = ""

    try:
        lines = content.splitlines()
        mode = None
        buffer = []

        for line in lines:
            line_strip = line.strip()
            if "1️⃣ Company Summary:" in line_strip:
                if buffer and mode == "company_summary":
                    company_summary = " ".join(buffer)
                    buffer = []
                mode = "company_summary"
            elif "2️⃣ Industry/Field:" in line_strip:
                if buffer and mode == "company_summary":
                    company_summary = " ".join(buffer)
                    buffer = []
                mode = "industry"
            elif "3️⃣ Ideal Target Audience:" in line_strip:
                if buffer and mode == "industry":
                    industry = " ".join(buffer)
                    buffer = []
                mode = "ideal_targets"
            elif "4️⃣ Best Outreach Angles:" in line_strip:
                if buffer and mode == "ideal_targets":
                    ideal_targets = "\n".join(buffer)
                    buffer = []
                mode = "outreach_angles"
            elif "5️⃣ Cold Emails:" in line_strip:
                if buffer and mode == "outreach_angles":
                    outreach_angles = "\n".join(buffer)
                    buffer = []
                mode = "emails"
            elif "📧 Professional Email Subject:" in line_strip:
                prof_subject = line_strip.replace("📧 Professional Email Subject:", "").strip()
                mode = "prof_body"
                buffer = []
            elif "📨 Professional Email Body:" in line_strip:
                mode = "prof_body_collect"
                buffer = []
            elif "📧 Humble & Conversational Email Subject:" in line_strip:
                if buffer and mode == "prof_body_collect":
                    prof_body = "\n".join(buffer)
                    buffer = []
                humble_subject = line_strip.replace("📧 Humble & Conversational Email Subject:", "").strip()
                mode = "humble_body"
            elif "📨 Humble & Conversational Email Body:" in line_strip:
                mode = "humble_body_collect"
                buffer = []
            else:
                if mode in ["company_summary", "industry", "ideal_targets", "outreach_angles", "prof_body_collect", "humble_body_collect"]:
                    buffer.append(line_strip)

        # Capture remaining buffers
        if buffer and mode == "humble_body_collect":
            humble_body = "\n".join(buffer)

    except Exception as e:
        st.warning(f"Parsing error: {e}")

    return company_summary, industry, ideal_targets, outreach_angles, prof_subject, prof_body, humble_subject, humble_body

# -------------------------
# Single URL Analysis
# -------------------------
def analyze_single_url():
    url = st.text_input("Enter Website URL:")
    if st.button("Analyze"):
        if url:
            st.subheader("📌 Generating Analysis & Emails...")
            text = scrape_website(url)
            content = groq_ai_analyze(url, text)

            company_summary, industry, ideal_targets, outreach_angles, prof_subject, prof_body, humble_subject, humble_body = parse_analysis(content)

            # Display Company Analysis
            st.subheader("🏢 Company Analysis")
            st.markdown(f"**Company Summary:** {company_summary}")
            st.markdown(f"**Industry/Field:** {industry}")
            st.markdown(f"**Ideal Target Audience:**\n{ideal_targets}")
            st.markdown(f"**Best Outreach Angles:**\n{outreach_angles}")

            # Display Emails fully expanded
            st.subheader("✉️ Professional Email")
            st.text_area("Copy & Paste Ready Email", f"📧 Email Subject:\n{prof_subject}\n\n📨 Email Body:\n{prof_body}", height=max(300, len(prof_body.splitlines())*25))

            st.subheader("✉️ Humble & Conversational Email")
            st.text_area("Copy & Paste Ready Email", f"📧 Email Subject:\n{humble_subject}\n\n📨 Email Body:\n{humble_body}", height=max(300, len(humble_body.splitlines())*25))

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
                content = groq_ai_analyze(url, text)

                company_summary, industry, ideal_targets, outreach_angles, prof_subject, prof_body, humble_subject, humble_body = parse_analysis(content)

                results.append({
                    "url": url,
                    "company_summary": company_summary,
                    "industry": industry,
                    "ideal_targets": ideal_targets,
                    "outreach_angles": outreach_angles,
                    "professional_subject": prof_subject,
                    "professional_body": prof_body,
                    "humble_subject": humble_subject,
                    "humble_body": humble_body
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
st.title("🌐 Website Outreach AI Agent (Groq) – Company Analysis + Cold Emails")

mode = st.radio("Select Mode", ["Single URL", "Bulk CSV Upload"])

if mode == "Single URL":
    analyze_single_url()
else:
    analyze_bulk()
