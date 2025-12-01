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
# Groq AI API Call
# -------------------------
def groq_ai_analyze(url, text, style):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""
You are a B2B sales outreach AI Agent.
Analyze the company using the URL and scraped content below.

Your response MUST begin with ONLY the following JSON structure (no extra words):

{{
"company_summary": "2-3 line summary",
"main_products": ["service 1", "service 2", "service 3"],
"ideal_customers": ["ICP 1", "ICP 2", "ICP 3"],
"outreach_angles": ["angle 1", "angle 2", "angle 3"]
}}

After that JSON block, generate:

Subject Line:
- Clear, specific, value-driven (no emojis)

Email Body:
(Tone: {style})
(Use this format EXACTLY — no additional text before or after)

Hi [First Name],

Are you looking for an updated and verified list of leads in the {{industry}} industry?

Our database includes:
- {{ICP1}}
- {{ICP2}}
- {{ICP3}}
- {{ICP4}}
- {{ICP5}}

Each contact includes name, title, email, phone, and company/need insights — helping you connect directly with the right decision makers.

I’d be happy to share additional details and a few sample records tailored for your review.

Would you like me to send them over?

Best regards,

Website: {url}

Scraped Content:
{text}
"""

    body = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.65
    }

    try:
        r = requests.post(API_URL, headers=headers, json=body)
        res = r.json()

        if "choices" not in res:
            return f"❌ Unexpected Response: {json.dumps(res)}"

        return res["choices"][0]["message"]["content"]

    except Exception as e:
        return f"⚠️ API Error: {e}"


# -------------------------
# Parse Email
# -------------------------
def parse_email(content):
    subject = ""
    body = ""

    lines = content.splitlines()
    found_subject = False

    for i, line in enumerate(lines):
        if line.strip().lower().startswith("subject"):
            subject = line.split(":", 1)[-1].strip()
            found_subject = True
            continue

        if found_subject:
            # Skip empty lines
            if line.strip() == "":
                continue
            # Capture rest of content as body
            body = "\n".join(lines[i:]).strip()
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

            st.subheader("⏳ AI Processing... Please wait")

            prof = groq_ai_analyze(url, scraped, "Professional")
            conv = groq_ai_analyze(url, scraped, "Conversational")

            insights_json = extract_json(prof)

            if insights_json:
                insights_display = (
                    f"📌 Company Summary:\n{insights_json['company_summary']}\n\n"
                    f"🏷️ Key Products:\n- " + "\n- ".join(insights_json['main_products']) + "\n\n"
                    f"🎯 Ideal Customers:\n- " + "\n- ".join(insights_json['ideal_customers']) + "\n\n"
                    f"💡 Outreach Angles:\n- " + "\n- ".join(insights_json['outreach_angles'])
                )
            else:
                insights_display = "⚠️ Insights unavailable — Try again"

            sp, bp = parse_email(prof)
            sh, bh = parse_email(conv)

            st.subheader("🏢 Company Insights")
            st.text_area("Insights", insights_display, height=300)

            st.subheader("1️⃣ Professional Email — Copy & Paste Ready")
            st.text_area("Professional Email", f"Subject: {sp}\n\n{bp}", height=650)

            st.subheader("2️⃣ Conversational Email — Copy & Paste Ready")
            st.text_area("Conversational Email", f"Subject: {sh}\n\n{bh}", height=650)


# -------------------------
# Bulk CSV Mode
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
                scraped = scrape_website(url)

                prof = groq_ai_analyze(url, scraped, "Professional")
                conv = groq_ai_analyze(url, scraped, "Conversational")

                sp, bp = parse_email(prof)
                sh, bh = parse_email(conv)

                results.append({
                    "url": url,
                    "professional_subject": sp,
                    "professional_body": bp,
                    "conversational_subject": sh,
                    "conversational_body": bh
                })

                progress.progress((i + 1) / len(df))

            result_df = pd.DataFrame(results)
            st.success("Bulk Analysis Completed!")
            st.dataframe(result_df)

            st.download_button(
                "Download Results CSV",
                result_df.to_csv(index=False).encode("utf-8"),
                "results.csv",
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
