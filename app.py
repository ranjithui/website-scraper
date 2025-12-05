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

# Scrape Website Content
def scrape_website(url):
    try:
        if not url.startswith("http"):
            url = "https://" + url
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        return text[:4000]
    except Exception as e:
        st.warning(f"Failed to scrape {url}: {e}")
        return ""

# Extract JSON
def extract_json(content):
    try:
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
    except:
        return None

# AI Insights Only
def groq_ai_generate_insights(url, text):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    prompt = f"""
You are a business analyst. Extract ONLY JSON insights.

Return in this exact JSON format:

{{
"company_name": "Company Name",
"company_summary": "2-3 line summary",
"main_products": ["service 1", "service 2"],
"ideal_customers": ["ICP1", "ICP2"],
"ideal_audience": ["audience1", "audience2"],
"industry": "best guess industry",
"countries_of_operation": ["Country1", "Country2"]
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
        return r.json()["choices"][0]["message"]["content"]
    except:
        return ""

# AI Email Generator
def groq_ai_generate_email(url, text, tone, insights):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    company_name = insights.get("company_name", "This Company")
    industry = insights.get("industry", "your industry")
    ideal_customers = insights.get("ideal_customers", [])
    countries = ", ".join(insights.get("countries_of_operation", []))

    customers_bullets = "\n• ".join(ideal_customers) if ideal_customers else "• Your best-fit customers"

    if "professional" in tone.lower():
        prompt = f"""
Return ONLY the below email:

Subject: Quick idea that may support {company_name}

Hello [First Name],

I noticed {company_name} is doing strong work in {industry} and operating across {countries}.
We support teams like yours connect faster with key decision-makers:

• {customers_bullets}

If it’s useful, I’d be happy to share a short sample — completely optional.

Regards,
Ranjith
"""
    else:
        prompt = f"""
Return ONLY the below email:

Subject: Quick idea for {company_name} 🚀

Hi [First Name],

Saw {company_name} expanding in {countries} — love the direction you are growing in {industry}!  
We help teams like yours speed up outreach to the right decision-makers 👇

• {customers_bullets}

Happy to send a small sample — zero pressure 🙂  

Cheers,  
Ranjith 🚀
"""

    body = {"model": MODEL_NAME, "messages": [{"role": "user", "content": prompt}], "temperature": 0.55}

    try:
        r = requests.post(API_URL, headers=headers, json=body)
        email = r.json()["choices"][0]["message"]["content"]
        return smart_filter(email)
    except:
        return ""

# Email parser
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


# Bulk Mode (with index reset fix)
def analyze_bulk():

    file = st.file_uploader("Upload CSV or Excel with 'Website' column", type=["csv", "xlsx", "xls"])

    if file is None:
        return

    # Reset index when new file uploaded
    if "last_uploaded_file" not in st.session_state or st.session_state.last_uploaded_file != file.name:
        st.session_state.bulk_index = 0
        st.session_state.last_uploaded_file = file.name

    file_name = file.name.lower()
    if file_name.endswith(".csv"):
        try:
            df = pd.read_csv(file, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(file, encoding="latin1", errors="ignore")
    else:
        df = pd.read_excel(file, engine="openpyxl")

    if "Website" not in df.columns:
        st.error("CSV/Excel must contain 'Website' column")
        return

    if "bulk_index" not in st.session_state:
        st.session_state.bulk_index = 0

    index = st.session_state.bulk_index

    if index >= len(df):
        st.success("🎉 All URLs processed!")
        return

    url = df.loc[index, "Website"]
    st.info(f"Processing {index+1}/{len(df)} → {url}")

    # Only showing these 4 fields (unchanged)
    first_name = df.loc[index].get("First Name", "N/A")
    last_name = df.loc[index].get("Last Name", "N/A")
    company_name_csv = df.loc[index].get("Company Name", "N/A")
    email = df.loc[index].get("Email", "N/A")

    st.subheader("📌 Contact Details")
    st.write(f"**First Name:** {first_name}")
    st.write(f"**Last Name:** {last_name}")
    st.write(f"**Company Name:** {company_name_csv}")
    st.write(f"**Email:** {email}")

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

    if insights.get("countries_of_operation"):
        st.markdown("### 🌍 Countries of Operation")
        for c in insights["countries_of_operation"]:
            st.write(f"- {c}")

    st.subheader("1️⃣ Professional Tone Email")
    st.text_area("Professional", f"Subject: {sp}\n\n{bp}", height=220)

    st.subheader("2️⃣ Friendly Tone Email")
    st.text_area("Friendly", f"Subject: {sf}\n\n{bf}", height=220)

    if st.button("Next Website ➜"):
        st.session_state.bulk_index += 1
        st.rerun()

# UI
st.title("🌐 Website Outreach AI Agent (Groq)")
mode = st.radio("Select Mode", ["Bulk CSV Upload"])

if mode == "Bulk CSV Upload":
    analyze_bulk()
