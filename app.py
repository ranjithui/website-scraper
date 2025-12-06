import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import re
import time
import random
import hashlib

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="Website Outreach AI Agent", layout="wide")

# -------------------------
# Load API key (do NOT expose)
# -------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL_NAME = "llama-3.3-70b-versatile"

# -------------------------
# Smart Spam Filter
# -------------------------
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
    if not text:
        return text
    for pattern, replacement in spam_words_map.items():
        text = re.sub(pattern, replacement, text)
    return text

# -------------------------
# Scrape Website Content
# -------------------------
def scrape_website(url):
    try:
        if not url.startswith("http"):
            url = "https://" + url
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, timeout=20, headers=headers)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        return soup.get_text(separator=" ", strip=True)[:4000]
    except:
        return ""

# -------------------------
# Extract JSON from AI response
# -------------------------
def extract_json(content):
    try:
        start, end = content.find("{"), content.rfind("}") + 1
        if start == -1 or end == -1:
            return None
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
        for k in defaults:
            data.setdefault(k, defaults[k])
        return data
    except:
        return None

# -------------------------
# Retry Wrapper
# -------------------------
def safe_api_call(func, *args, retries=3, backoff=2, **kwargs):
    for attempt in range(1, retries + 1):
        try:
            return func(*args, **kwargs)
        except:
            if attempt == retries:
                return None
            time.sleep(backoff * attempt + random.random())

# -------------------------
# AI Insights
# -------------------------
def groq_ai_generate_insights(url, text):
    if not GROQ_API_KEY:
        return ""
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    prompt = f"""
Extract ONLY JSON:

{{
"company_name": "Company Name",
"company_summary": "2-3 line summary",
"main_products": ["service1", "service2"],
"ideal_customers": ["ICP1", "ICP2"],
"ideal_audience": ["audience1", "audience2"],
"industry": "best guess industry",
"countries_of_operation": ["Country1", "Country2"]
}}

URL: {url}
CONTENT: {text}
"""
    body = {"model": MODEL_NAME, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3}
    try:
        r = requests.post(API_URL, headers=headers, json=body, timeout=30).json()
        return r["choices"][0]["message"]["content"]
    except:
        return ""

# -------------------------
# AI Email Pitch Generator
# -------------------------
def groq_ai_generate_email(url, text, pitch_type, insights):
    if not GROQ_API_KEY:
        return ""

    company_name = insights.get("company_name", "This Company")
    industry = insights.get("industry", "your industry")
    products = ", ".join(insights.get("main_products", [])) or "your offerings"
    ic = "\n".join(insights.get("ideal_customers", [])) or "Your best-fit customers"
    ia = "\n".join(insights.get("ideal_audience", [])) or "Your target audience"
    countries = ", ".join(insights.get("countries_of_operation", [])) or "multiple regions"

    if pitch_type == "Professional":
        prompt = f"""
Subject: {company_name}

Hi [First Name],

I noticed {company_name} is doing excellent work in {industry}, offering: {products}, across {countries}.  
We help teams like yours connect faster with key decision-makers:

• Ideal Customers:
{ic}

• Ideal Audience:
{ia}

Would you like a short sample to explore?

Regards,  
Ranjith
"""
    elif pitch_type == "LinkedIn":
        prompt = f"""
Hi [First Name], I came across {company_name} — strong presence in {industry}, offering: {products}.  

We can help you reach:
• Customers: {ic.replace('\n', ', ')}
• Audience: {ia.replace('\n', ', ')}

Interested in a quick example?  
— Ranjith
"""
    else:
        return ""

    body = {"model": MODEL_NAME, "messages": [{"role": "user", "content": prompt}], "temperature": 0.55}
    try:
        r = requests.post(API_URL, headers=headers, json=body, timeout=30).json()
        return smart_filter(r["choices"][0]["message"]["content"])
    except:
        return ""

# -------------------------
# Email Formatting
# -------------------------
def parse_email(content):
    subject, body = "", content
    if content.lower().startswith("subject:"):
        parts = content.split("\n", 1)
        subject = parts[0].split(":", 1)[1].strip()
        body = parts[1]
    return subject, body

def format_pitch_markdown(subject, body):
    return f"**Subject:** {subject}\n\n{body}"

# -------------------------
# Bulk Mode
# -------------------------
def analyze_bulk():
    file = st.file_uploader("Upload CSV/Excel with 'Website' column", type=["csv", "xlsx"])
    if not file:
        return

    if file.name.endswith(".csv"):
        df = pd.read_csv(file, encoding_errors="ignore")
    else:
        df = pd.read_excel(file)

    if "Website" not in df:
        st.error("Missing 'Website' column")
        return

    if "bulk_index" not in st.session_state:
        st.session_state.bulk_index = 0

    total = len(df)
    idx = st.session_state.bulk_index
    if idx >= total:
        st.success("All rows done!")
        return

    row = df.loc[idx]
    url = str(row["Website"])
    fname = row.get("First Name", "There")
    cname = row.get("Company Name", "")

    st.write(f"Row {idx+1}/{total}: **{url}**")

    scraped = scrape_website(url)
    insights = extract_json(safe_api_call(groq_ai_generate_insights, url, scraped)) or {}

    st.json(insights)

    for pitch in ["Professional", "LinkedIn"]:
        email = safe_api_call(groq_ai_generate_email, url, scraped, pitch, insights)
        email = email.replace("[First Name]", str(fname))

        subject, body = parse_email(email)
        if cname:
            subject = cname

        st.subheader(f"{pitch} Pitch")
        st.markdown(format_pitch_markdown(subject, body))

    if st.button("Next ➜"):
        st.session_state.bulk_index += 1
        st.rerun()

# -------------------------
# Single Mode
# -------------------------
def analyze_single():
    url = st.text_input("Enter Website URL")
    if st.button("Analyze"):
        scraped = scrape_website(url)
        insights = extract_json(safe_api_call(groq_ai_generate_insights, url, scraped)) or {}
        st.json(insights)

        for pitch in ["Professional", "LinkedIn"]:
            email = safe_api_call(groq_ai_generate_email, url, scraped, pitch, insights)
            st.subheader(f"{pitch} Pitch")
            st.markdown(email)

# -------------------------
# UI
# -------------------------
st.title("🌐 Website Outreach AI Agent")

mode = st.radio("Mode", ["Single URL", "Bulk CSV Upload"])
if mode == "Single URL":
    analyze_single()
else:
    analyze_bulk()
