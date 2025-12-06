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
# Scrape Website
# -------------------------
def scrape_website(url):
    try:
        if not url:
            return ""
        if not url.startswith("http"):
            url = "https://" + url
        headers = {"User-Agent": "Mozilla/5.0 (compatible; OutreachAgent/1.0)"}
        r = requests.get(url, timeout=20, headers=headers)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        return soup.get_text(separator=" ", strip=True)[:4000]
    except Exception:
        return ""

# -------------------------
# Extract JSON insights
# -------------------------
def extract_json(content):
    try:
        if not content:
            return None
        start = content.find("{")
        end = content.rfind("}") + 1
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
        for k, v in defaults.items():
            if k not in data:
                data[k] = v
        return data
    except Exception:
        return None

# -------------------------
# Safe API wrapper
# -------------------------
def safe_api_call(func, *args, retries=3, backoff=2, **kwargs):
    for attempt in range(1, retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception:
            if attempt == retries: return None
            time.sleep(backoff * attempt + random.random())
    return None

# -------------------------
# AI Insights Generator
# -------------------------
def groq_ai_generate_insights(url, text):
    if not GROQ_API_KEY:
        return ""
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    prompt = f"""
You are a business analyst. Extract ONLY JSON insights in EXACT format:

{{
"company_name": "Company Name",
"company_summary": "2-3 line summary",
"main_products": ["service 1", "service 2"],
"ideal_customers": ["ICP1", "ICP2"],
"ideal_audience": ["audience1", "audience2"],
"industry": "best guess industry",
"countries_of_operation": ["Country1", "Country2"]
}}

URL: {url}
Content: {text}
"""
    body = {"model": MODEL_NAME, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3}
    try:
        r = requests.post(API_URL, headers=headers, json=body, timeout=30)
        return r.json()["choices"][0]["message"]["content"]
    except Exception:
        return ""

# -------------------------
# Email Generator (2 pitches only)
# -------------------------
def groq_ai_generate_email(url, text, pitch_type, insights):
    if not GROQ_API_KEY:
        return ""
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}

    company = insights.get("company_name", "This Company")
    industry = insights.get("industry", "industry")
    products = ", ".join(insights.get("main_products", []))
    customers = "\n".join(insights.get("ideal_customers", []))
    audience = "\n".join(insights.get("ideal_audience", []))
    countries = ", ".join(insights.get("countries_of_operation", []))

    if pitch_type.lower() == "professional":
        prompt = f"""
Subject: {company}

Hi [First Name],

I noticed {company} is doing great work in {industry}, especially with {products} across {countries}.
We help companies like yours connect faster with:

• Ideal Customers:
{customers}

• Ideal Audience:
{audience}

Would you like a short sample to review?

Regards,  
Ranjith
"""
    elif pitch_type.lower() == "linkedin":
        prompt = f"""
Hi [First Name],

I noticed {company} excels in {industry} with {products}.
We help teams connect with:
• Ideal Customers
• Ideal Audience

Open to a quick sample?

— Ranjith
"""
    else:
        return ""

    body = {"model": MODEL_NAME, "messages": [{"role": "user", "content": prompt}], "temperature": 0.55}

    try:
        r = requests.post(API_URL, headers=headers, json=body, timeout=30)
        return smart_filter(r.json()["choices"][0]["message"]["content"])
    except Exception:
        return ""

# -------------------------
# Parse + Format Email
# -------------------------
def parse_email(content):
    if not content:
        return "", ""
    subject = ""
    body = ""
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.lower().startswith("subject:"):
            subject = line.split(":", 1)[1].strip()
            body = "\n".join(lines[i+1:]).strip()
            break
    return subject, body

def format_pitch_markdown(subject, body):
    return f"**Subject:** {subject}\n\n{body}"

# -------------------------
# BULK MODE
# -------------------------
def analyze_bulk():
    file = st.file_uploader("Upload CSV/Excel with 'Website'", type=["csv", "xlsx", "xls"])
    if file is None: return

    file_hash = hashlib.md5(file.getvalue()).hexdigest()
    if st.session_state.get("last_file_hash") != file_hash:
        st.session_state.bulk_index = 0
        st.session_state.last_file_hash = file_hash

    df = pd.read_csv(file) if file.name.endswith(".csv") else pd.read_excel(file)
    if "Website" not in df.columns:
        st.error("Missing 'Website' column")
        return

    total = len(df)
    idx = st.session_state.get("bulk_index", 0)
    idx_input = st.number_input("Row #", 1, total, idx+1)
    if st.button("Jump"):
        st.session_state.bulk_index = idx_input - 1
        st.rerun()

    if idx >= total:
        st.success("All rows completed")
        return

    row = df.loc[idx]
    url = row["Website"]
    first = row.get("First Name", "There")

    st.info(f"Row {idx+1}/{total} → {url}")

    scraped = scrape_website(url)
    insights_raw = safe_api_call(groq_ai_generate_insights, url, scraped)
    insights = extract_json(insights_raw) or {}

    st.json(insights)

    pitch_types = ["Professional", "LinkedIn"]  # ← Only 2 pitches

    for pt in pitch_types:
        email = safe_api_call(groq_ai_generate_email, url, scraped, pt, insights)
        if not email:
            st.warning(f"{pt} pitch missing.")
            continue

        email = email.replace("[First Name]", str(first))

        if pt.lower() == "linkedin":
            st.subheader("LinkedIn Pitch")
            st.markdown(email)
        else:
            subject, body = parse_email(email)
            company_csv = row.get("Company Name", "")
            if company_csv and company_csv != "nan":
                subject = str(company_csv)
            st.subheader(f"{pt} Pitch")
            st.markdown(format_pitch_markdown(subject, body))

    col1, col2 = st.columns(2)
    if col1.button("Next ➜"):
        st.session_state.bulk_index += 1
        st.rerun()
    if col2.button("Skip ➜"):
        st.session_state.bulk_index += 1
        st.rerun()

# -------------------------
# SINGLE URL MODE
# -------------------------
def analyze_single():
    url = st.text_input("Website")
    if st.button("Analyze"):
        scraped = scrape_website(url)
        insights_raw = safe_api_call(groq_ai_generate_insights, url, scraped)
        insights = extract_json(insights_raw) or {}
        st.json(insights)

        pitch_types = ["Professional", "LinkedIn"]  # ← Only 2 pitches

        for pt in pitch_types:
            email = safe_api_call(groq_ai_generate_email, url, scraped, pt, insights)
            if pt.lower() == "linkedin":
                st.subheader("LinkedIn Pitch")
                st.markdown(email)
            else:
                subject, body = parse_email(email)
                st.subheader(f"{pt} Pitch")
                st.markdown(format_pitch_markdown(subject, body))

# -------------------------
# MAIN
# -------------------------
st.title("🌐 Website Outreach AI Agent (Groq)")

mode = st.radio("Choose Mode", ["Single URL", "Bulk CSV Upload"])
if mode == "Single URL":
    analyze_single()
else:
    analyze_bulk()
