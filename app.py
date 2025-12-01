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

Task: Analyze the company using the URL and scraped content below.

Deliver 3 structured outputs:

1️⃣ Company Insights
- 2–3 line overview of what the company does
- 3 bullet points listing their main services/products
- 3 bullet points listing the Ideal Customer Profile (ICP)

2️⃣ Best Outreach Angles
- 2–3 bullets explaining how **targeted B2B email lists** can help them

3️⃣ Cold Email (Professional Format)
Format:
📧 Subject Line:
📝 Email Body:
- Well formatted with bullet points and bold key value propositions
- Add a single clear CTA with a **sample email list offer**
- Maintain 6–9 concise sentences

Website: {url}

Scraped Content:
{text}
"""
    else:
        prompt = f"""
You are a B2B sales outreach AI Agent.

Task: Analyze the company using the URL and scraped content below.

Deliver 3 structured outputs:

1️⃣ Company Insights
- 2–3 line overview of what the company does
- 3 bullet points listing their main services/products
- 3 bullet points listing the Ideal Customer Profile (ICP)

2️⃣ Best Outreach Angles
- 2–3 bullets, friendly tone

3️⃣ Cold Email (Conversational Style)
Format:
📧 Subject Line:
📝 Email Body:
- Polite, human tone
- Include **targeted B2B email lists**
- Clear CTA offering a **sample list**

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

        return response["choices"][0]["message"]["content"]

    except Exception as e:
        return f"⚠️ API Error: {e}"

# -------------------------
# Parse Email (Subject + Body)
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
            if "📧" in line_strip:
                email_subject = line_strip.replace("📧 Subject Line:", "").replace("📧 Email Subject:", "").strip()
                mode = "email_body"
                buffer = []
            elif "📝 Email Body" in line_strip or "📨 Email Body" in line_strip:
                mode = "email_body"
                buffer = []
            elif mode == "email_body":
                buffer.append(line_strip)
        email_body = "\n".join(buffer)
    except:
        pass
    return email_subject, email_body

# -------------------------
# Parse Insights Section
# -------------------------
def parse_insights(content):
    try:
        part = content.split("1️⃣ Company Insights")[1]
        insights = part.split("2️⃣")[0].strip()
        return insights
    except:
        return "Insights not detected"

# -------------------------
# Single URL Analysis
# -------------------------
def analyze_single_url():
    url = st.text_input("Enter Website URL:")
    if st.button("Analyze"):
        if url:
            text = scrape_website(url)

            st.subheader("📌 Generating Results... Please wait ⏳")

            # AI Calls
            content_prof = groq_ai_analyze(url, text, "Professional")
            content_humble = groq_ai_analyze(url, text, "Humble & Conversational")

            # Parse
            insights_prof = parse_insights(content_prof)

            subject_prof, body_prof = parse_analysis(content_prof)
            subject_humble, body_humble = parse_analysis(content_humble)

            st.subheader("🏢 Company Insights")
            st.text_area("Insights", insights_prof, height=250)

            st.subheader("1️⃣ Professional Email")
            st.text_area(
                "Professional Cold Email",
                f"📧 Email Subject: {subject_prof}\n\n📝 Email Body:\n{body_prof}",
                height=650
            )

            st.subheader("2️⃣ Humble & Conversational Email")
            st.text_area(
                "Conversational Cold Email",
                f"📧 Email Subject: {subject_humble}\n\n📝 Email Body:\n{body_humble}",
                height=650
            )

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

                content_prof = groq_ai_analyze(url, text, "Professional")
                content_humble = groq_ai_analyze(url, text, "Humble & Conversational")

                subject_prof, body_prof = parse_analysis(content_prof)
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
