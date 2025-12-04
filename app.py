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

# Smart Spam Filter
spam_words_map = {
    r"(?i)\bbuy\b": "explore",
    r"(?i)\bbulk\b": "high-volume",
    r"(?i)\bemail list\b": "decision-maker contacts",
    r"(?i)\bguarantee\b": "support",
    r"(?i)\bcheap\b": "budget-friendly",
    r"(?i)\bfree leads\b": "sample contacts",
    r"(?i)\bpurchase\b": "access",
    r"(?i)\bno risk\b": "no pressure",
    r"(?i)\bspecial offer\b": "focused support",
    r"(?i)\bmarketing list\b": "targeted contacts",
    r"(?i)\brisk-free\b": "optional",
}

def smart_filter(text):
    for pattern, replacement in spam_words_map.items():
        text = re.sub(pattern, replacement, text)
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
        if start == -1 or end == -1:
            return None
        data = json.loads(content[start:end])
        if "company_name" not in data:
            data["company_name"] = "This Company"
        if "company_summary" not in data:
            data["company_summary"] = "A growing organization"
        if "main_products" not in data:
            data["main_products"] = []
        if "ideal_customers" not in data:
            data["ideal_customers"] = []
        if "industry" not in data:
            data["industry"] = "General"
        if "ideal_audience" not in data:
            data["ideal_audience"] = []   # ← added
        return data
    except:
        return None

# -------------------------
# AI for Insights Only
# -------------------------
def groq_ai_generate_insights(url, text):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}","Content-Type": "application/json"}

    prompt = f"""
You are a business analyst. Extract ONLY JSON insights from the website.

Return in this exact JSON format:

{{
"company_name": "Company Name",
"company_summary": "2-3 line summary",
"main_products": ["service 1", "service 2"],
"ideal_customers": ["ICP1", "ICP2"],
"ideal_audience": ["audience1", "audience2"],
"industry": "best guess industry"
}}

Company URL: {url}
Website Content: {text}
"""

    body = {"model": MODEL_NAME,"messages": [{"role": "user","content": prompt}],"temperature": 0.3}

    try:
        r = requests.post(API_URL, headers=headers, json=body)
        res = r.json()
        return res["choices"][0]["message"]["content"]
    except:
        return ""

# -------------------------
# AI for Emails Only
# -------------------------
def groq_ai_generate_email(url, text, tone, insights):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}","Content-Type": "application/json"}

    company_name = insights.get("company_name", "This Company")
    main_products = ", ".join(insights.get("main_products", []))
    industry = insights.get("industry", "Your industry")
    ideal_customers = insights.get("ideal_customers", [])
    customers_bullets = "\n• ".join(ideal_customers) if ideal_customers else "• Your ideal customers"

    if "professional" in tone.lower():
        prompt = f"""
Return ONLY the below structured email:

Subject: Quick idea that may support {company_name}

Hello [First Name],

I noticed {company_name} is doing amazing work in {industry}, especially around {main_products}.
We help teams like yours connect faster with key decision-makers:

• {customers_bullets}

If it’s useful, I’d be happy to share a short sample — completely optional.

Regards,
Ranjith
"""
    else:
        prompt = f"""
Return ONLY the below structured email:

Subject: Quick idea for {company_name} 🚀

Hi [First Name],

Checked out {company_name} — love the direction you’re moving in {industry}!  
We help brands like yours speed up outreach to your best-fit decision-makers 👇

• {customers_bullets}

Happy to send a small sample so you can see the match — zero pressure 🙂

Cheers,  
Ranjith 🚀
"""

    body = {"model": MODEL_NAME,"messages": [{"role": "user","content": prompt}],"temperature": 0.55}

    try:
        r = requests.post(API_URL, headers=headers, json=body)
        email = r.json()["choices"][0]["message"]["content"]
        return smart_filter(email)
    except:
        return ""

# -------------------------
# Parse Subject/Email Body
# -------------------------
def parse_email(content):
    subject = ""
    body = ""
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.lower().startswith("subject:"):
            subject = line.split(":",1)[1].strip()
            body = "\n".join(lines[i+1:]).strip()
            break
    return subject, body

# -------------------------
# Single URL Mode
# -------------------------
def analyze_single_url():
    url = st.text_input("Enter Website URL:")

    if st.button("Analyze"):
        scraped = scrape_website(url)
        insights_raw = groq_ai_generate_insights(url, scraped)
        insights = extract_json(insights_raw)

        prof_email = groq_ai_generate_email(url, scraped, "Professional", insights)
        friendly_email = groq_ai_generate_email(url, scraped, "Friendly", insights)

        sp, bp = parse_email(prof_email)
        sf, bf = parse_email(friendly_email)

        st.subheader("📌 Company Insights")
        st.json(insights)

        if insights.get("ideal_audience"):
            st.markdown("### 🎯 Ideal Audience")
            for a in insights["ideal_audience"]:
                st.write(f"- {a}")

        st.subheader("1️⃣ Professional Corporate Tone")
        st.text_area("Professional", f"Subject: {sp}\n\n{bp}", height=220)

        st.subheader("2️⃣ Friendly Conversational Tone")
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

                p = groq_ai_generate_email(url, scraped, "Professional", insights)
                f = groq_ai_generate_email(url, scraped, "Friendly", insights)

                sp, bp = parse_email(p)
                sf, bf = parse_email(f)

                results.append({
                    "url": url,
                    "company_name": insights.get("company_name") if insights else "",
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
