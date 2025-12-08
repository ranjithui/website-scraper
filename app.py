import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import re
import time
import base64

st.set_page_config(page_title="Website Outreach AI Agent", layout="wide")

# Load API key
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL_NAME = "llama-3.3-70b-versatile"


# -------------------------- SMART SPAM FILTER --------------------------
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


# -------------------------- SCRAPING --------------------------
def scrape_website(url):
    try:
        if not url.startswith("http"):
            url = "https://" + url

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        r = requests.get(url, timeout=15, headers=headers)

        if len(r.text) < 200:
            return "Website content not accessible or protected."

        soup = BeautifulSoup(r.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()

        text = " ".join(soup.stripped_strings)

        return text[:8000]

    except Exception as e:
        st.warning(f"Failed to scrape {url}: {e}")
        return ""


# -------------------------- AI EXTRACTION --------------------------
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

    body = {"model": MODEL_NAME, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3}
    try:
        r = requests.post(API_URL, headers=headers, json=body)
        return r.json()["choices"][0]["message"]["content"]
    except:
        return ""


def groq_ai_generate_email(url, text, pitch_type, insights):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}

    company_name = insights.get("company_name", "This Company")
    industry = insights.get("industry", "your industry")
    main_products = insights.get("main_products", [])
    ideal_customers = insights.get("ideal_customers", [])
    ideal_audience = insights.get("ideal_audience", [])
    countries = ", ".join(insights.get("countries_of_operation", []))

    products_text = ", ".join(main_products) if main_products else "your services/products"

    if pitch_type.lower() == "professional":
        prompt = f"""
Subject: {company_name}

Hi [First Name],

I noticed {company_name} is doing excellent work in {industry}, offering: {products_text}, across {countries}.  
We help teams like yours connect faster with the decision-makers who matter most.

Would you like a short sample?

Regards,  
Ranjith
"""
    elif pitch_type.lower() == "results":
        prompt = f"""
Subject: {company_name}

Hello [First Name],

Companies in {industry} offering {products_text} using our database have seen measurable improvements connecting with decision-makers.

I’d be happy to share a tailored example.

Regards,  
Ranjith
"""
    elif pitch_type.lower() == "data":
        prompt = f"""
Subject: {company_name}

Hi [First Name],

Our curated database ensures you reach verified decision-makers relevant to {industry} and its offerings: {products_text}.

Would you like a short sample to see quality?

Thanks,  
Ranjith
"""
    elif pitch_type.lower() == "linkedin":
        prompt = f"""
Hi [First Name],

I noticed {company_name} excels in {industry}, offering: {products_text}.  
We help expand outreach to decision-makers.

Would you like a quick example?

— Ranjith
"""
    else:
        return "Invalid pitch type"

    body = {"model": MODEL_NAME, "messages": [{"role": "user", "content": prompt}], "temperature": 0.5}

    try:
        r = requests.post(API_URL, headers=headers, json=body)
        email = r.json()["choices"][0]["message"]["content"]
        return smart_filter(email)
    except:
        return ""


# -------------------------- BULK MODE WITH AUTO TIMER --------------------------
def analyze_bulk():
    file = st.file_uploader("Upload CSV (must contain 'Website')", type=["csv", "xlsx", "xls"])
    if file is None:
        return

    # Load once
    if "bulk_df" not in st.session_state:
        file_name = file.name.lower()
        if file_name.endswith(".csv"):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)

        if "Website" not in df.columns:
            st.error("CSV must contain Website column")
            return

        df["Insights"] = ""
        df["Professional Pitch"] = ""
        df["Results Pitch"] = ""
        df["Data Pitch"] = ""
        df["LinkedIn Pitch"] = ""

        st.session_state.bulk_df = df
        st.session_state.bulk_index = 0
        st.session_state.last_run_time = 0

    df = st.session_state.bulk_df
    index = st.session_state.bulk_index

    if index >= len(df):
        st.success("🎉 All entries processed!")

        csv = df.to_csv(index=False)
        b64 = base64.b64encode(csv.encode()).decode()
        st.markdown(f"⬇️ Download Results: [Click Here](data:file/csv;base64,{b64})", unsafe_allow_html=True)
        return

    if time.time() - st.session_state.last_run_time < 30:
        remaining = int(30 - (time.time() - st.session_state.last_run_time))
        st.info(f"⏳ Waiting {remaining}s before next record...")
        st.experimental_rerun()

    url = df.loc[index, "Website"]
    st.warning(f"Processing {index+1}/{len(df)} — {url}")

    scraped = scrape_website(url)
    insights_raw = groq_ai_generate_insights(url, scraped)
    insights = extract_json(insights_raw)

    df.at[index, "Insights"] = json.dumps(insights, indent=2)

    for pt in ["Professional", "Results", "Data", "LinkedIn"]:
        df.at[index, f"{pt} Pitch"] = groq_ai_generate_email(url, scraped, pt, insights)

    st.session_state.bulk_df = df
    st.session_state.bulk_index += 1
    st.session_state.last_run_time = time.time()

    st.success(f"✔ Completed: {url}")
    st.experimental_rerun()


# -------------------------- SINGLE MODE --------------------------
def analyze_single():
    url = st.text_input("Enter Website URL")
    if st.button("Analyze"):
        scraped = scrape_website(url)
        insights_raw = groq_ai_generate_insights(url, scraped)
        insights = extract_json(insights_raw)

        st.subheader("Company Insights")
        st.json(insights)

        for pt in ["Professional", "Results", "Data", "LinkedIn"]:
            st.subheader(pt)
            st.write(groq_ai_generate_email(url, scraped, pt, insights))


# -------------------------- UI --------------------------
st.title("🌐 Website Outreach AI Agent (Groq)")

mode = st.radio("Mode", ["Single URL", "Bulk CSV Upload"])

if mode == "Single URL":
    analyze_single()
else:
    analyze_bulk()
