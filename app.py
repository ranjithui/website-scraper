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
# Spam-safe wording filter
# -------------------------
def apply_smart_filters(text):
    risk_words = [
        "free", "guaranteed", "earn", "money", "buy now",
        "exclusive offer", "urgent", "risk-free"
    ]
    for w in risk_words:
        text = text.replace(w, "", flags=None) if hasattr(text, 'replace') else text
    return text


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
        if "company_summary" not in data:
            data["company_summary"] = "A growing organization"

        # normalize audiences
        ideal = data.get("ideal_customers", [])
        target = data.get("target_audience", [])

        combined = []
        if isinstance(ideal, list):
            combined.extend(ideal)
        if isinstance(target, list):
            combined.extend(target)

        data["ideal_customers"] = list(dict.fromkeys(combined))  # merge unique

        if "industry" not in data:
            data["industry"] = "your industry"
        if "main_products" not in data:
            data["main_products"] = []

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
"main_products": ["service 1", "service 2", "service 3"],
"ideal_customers": ["ICP1", "ICP2", "ICP3"],
"target_audience": ["ICP1", "ICP2"],
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
# Call AI for Emails
# -------------------------
def groq_ai_generate_email(url, text, tone, insights):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    company = insights.get("company_name", "This Company")
    summary = insights.get("company_summary", "A growing organization")
    products = ", ".join(insights.get("main_products", [])) or "your offerings"
    industry = insights.get("industry", "your industry")

    icps = insights.get("ideal_customers", ["Decision makers in your space"])
    bullets = "\n• " + "\n• ".join(icps)

    if "professional" in tone.lower():  # Format A
        prompt = f"""
You are a B2B sales outreach expert.

Return ONLY the email in this EXACT format:

Subject: Updated Contacts for Investors & Decision-Makers at {company}

Hi [First Name],

I came across {company} while researching companies focused on {industry}. 
We’ve helped growth-focused companies strengthen outreach to:
{bullets}

If this aligns with your strategy, I’d be glad to share a verified sample list — so you can review it firsthand.

Looking forward to your thoughts,
Ranjith
"""
    else:  # Format B
        prompt = f"""
You are a B2B sales outreach expert.

Return ONLY the email in this EXACT format:

Subject: Connect with Key Buyers & Partners at {company}

Hi [First Name],  

I noticed {company} is focused on {products}.  
We help companies like yours connect with:
{bullets}

Would you be open to reviewing a quick sample list to see the exact fit?

Cheers!
Ranjith 🚀
"""

    body = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.55
    }

    try:
        r = requests.post(API_URL, headers=headers, json=body)
        email = r.json()["choices"][0]["message"]["content"]
        return apply_smart_filters(email)
    except:
        return ""


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

            insights_raw = groq_ai_generate_insights(url, scraped)
            insights = extract_json(insights_raw)

            prof_email = groq_ai_generate_email(url, scraped, "Professional Corporate Tone", insights)
            friendly_email = groq_ai_generate_email(url, scraped, "Friendly Conversational Tone", insights)

            sp, bp = parse_email(prof_email)
            sf, bf = parse_email(friendly_email)

            st.subheader("📌 Company Insights")
            st.json(insights)

            st.subheader("1️⃣ Professional Corporate Tone (A)")
            st.text_area("Professional", f"Subject: {sp}\n\n{bp}", height=220)

            st.subheader("2️⃣ Friendly Conversational Tone (B)")
            st.text_area("Friendly", f"Subject: {sf}\n\n{bf}", height=220)


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
st.title("🌐 Website Outreach AI Agent (Groq)")

mode = st.radio("Select Mode", ["Single URL", "Bulk CSV Upload"])

if mode == "Single URL":
    analyze_single_url()
else:
    analyze_bulk()
