import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import re

st.set_page_config(page_title="Website Outreach AI Agent", layout="wide")

# Load API Key
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL_NAME = "llama-3.3-70b-versatile"

# Spam Filter Words
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

# Website Scraper
def scrape_website(url):
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        return text[:4000]
    except Exception as e:
        st.warning(f"Failed to scrape {url}: {e}")
        return ""

# JSON Extraction
def extract_json(content):
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        data = json.loads(content[start:end])
        defaults = {
            "company_name": "This Company",
            "company_summary": "A growing organization",
            "main_products": [],
            "ideal_customers": [],
            "ideal_audience": [],
            "industry": "General",
            "countries_of_operation": []
        }
        for k,v in defaults.items():
            data.setdefault(k, v)
        return data
    except:
        return {
            "company_name": "This Company",
            "company_summary": "",
            "main_products": [],
            "ideal_customers": [],
            "ideal_audience": [],
            "industry": "Unknown",
            "countries_of_operation": []
        }

# AI - Generate Insights
def groq_ai_generate_insights(url, text):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    prompt = f"""
Extract ONLY the JSON insights:

{{
"company_name": "",
"company_summary": "",
"main_products": [],
"ideal_customers": [],
"ideal_audience": [],
"industry": "",
"countries_of_operation": []
}}

Website URL: {url}
Content: {text}
"""
    body = {"model": MODEL_NAME, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3}
    try:
        r = requests.post(API_URL, headers=headers, json=body)
        return r.json()["choices"][0]["message"]["content"]
    except:
        return "{}"

# AI - Generate Email
def groq_ai_generate_email(url, text, tone, insights):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    company_name = insights.get("company_name", "This Company")
    industry = insights.get("industry", "your industry")
    ideal_customers = insights.get("ideal_customers", [])
    countries = ", ".join(insights.get("countries_of_operation", []))

    customers_bullets = "\n• " + "\n• ".join(ideal_customers) if ideal_customers else "• Decision-makers in your target market"

    if tone == "Professional":
        prompt = f"""
Subject: Quick idea that may support {company_name}

Hello [First Name],

I noticed {company_name} is doing strong work in {industry} and operating across {countries}.
We support teams like yours connect faster with key decision-makers:

{customers_bullets}

If it’s useful, I’d be happy to share a short sample — completely optional.

Regards,
Ranjith
"""
    else:
        prompt = f"""
Subject: Quick idea for {company_name} 🚀

Hi [First Name],

Saw {company_name} expanding in {countries}! Love the direction in {industry}.  
We help teams like yours reach decision-makers faster 👇

{customers_bullets}

Happy to send a small sample — zero pressure 🙂  

Cheers,  
Ranjith 🚀
"""

    body = {"model": MODEL_NAME, "messages": [{"role": "user", "content": prompt}], "temperature": 0.45}
    try:
        r = requests.post(API_URL, headers=headers, json=body)
        return smart_filter(r.json()["choices"][0]["message"]["content"])
    except:
        return ""

# Email Parser
def parse_email(content):
    subject, body = "", ""
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.lower().startswith("subject:"):
            subject = line.split(":", 1)[1].strip()
            body = "\n".join(lines[i+1:]).strip()
            break
    return subject, body

###################################################
# Single URL Mode
###################################################
def analyze_single_url():
    url = st.text_input("Enter Website URL:")
    if st.button("Analyze Website"):
        scraped = scrape_website(url)
        insights_raw = groq_ai_generate_insights(url, scraped)
        insights = extract_json(insights_raw)

        prof_email = groq_ai_generate_email(url, scraped, "Professional", insights)
        friendly_email = groq_ai_generate_email(url, scraped, "Friendly", insights)

        sp, bp = parse_email(prof_email)
        sf, bf = parse_email(friendly_email)

        st.json(insights)

        if insights.get("ideal_audience"):
            st.markdown("### 🎯 Ideal Audience")
            for x in insights["ideal_audience"]:
                st.write(f"- {x}")

        if insights.get("countries_of_operation"):
            st.markdown("### 🌍 Countries of Operation")
            for x in insights["countries_of_operation"]:
                st.write(f"- {x}")

        st.subheader("Professional")
        st.text_area("Email 1", f"Subject: {sp}\n\n{bp}", height=200)
        st.subheader("Friendly")
        st.text_area("Email 2", f"Subject: {sf}\n\n{bf}", height=200)

###################################################
# Bulk CSV Mode
###################################################
def analyze_bulk():
    file = st.file_uploader("Upload CSV with 'Website' column", type=["csv"])
    if not file:
        return

    df = pd.read_csv(file)

    if "Website" not in df.columns:
        st.error("CSV must contain 'Website' column")
        return

    if "bulk_index" not in st.session_state:
        st.session_state.bulk_index = 0

    i = st.session_state.bulk_index

    if i >= len(df):
        st.success("🎉 All Websites Processed!")
        return

    url = df.loc[i, "Website"]
    st.info(f"Processing {i+1}/{len(df)} → {url}")

    # ⭐ Show full row data
    st.markdown("### 📄 Original Row Data")
    st.table(df.loc[[i]])

    scraped = scrape_website(url)
    insights_raw = groq_ai_generate_insights(url, scraped)
    insights = extract_json(insights_raw)

    prof_email = groq_ai_generate_email(url, scraped, "Professional", insights)
    friendly_email = groq_ai_generate_email(url, scraped, "Friendly", insights)

    sp, bp = parse_email(prof_email)
    sf, bf = parse_email(friendly_email)

    st.subheader("📌 Insights")
    st.json(insights)

    st.subheader("📧 Professional Email")
    st.text_area("Professional", f"Subject: {sp}\n\n{bp}", height=200)

    st.subheader("😄 Friendly Email")
    st.text_area("Friendly", f"Subject: {sf}\n\n{bf}", height=200)

    if st.button("Next ➜"):
        st.session_state.bulk_index += 1
        st.rerun()

###################################################
# UI Layout
###################################################
st.title("🌐 Website Outreach AI Agent (Groq)")

mode = st.radio("Select Mode", ["Single URL", "Bulk CSV Upload"])

if mode == "Single URL":
    analyze_single_url()
else:
    analyze_bulk()
