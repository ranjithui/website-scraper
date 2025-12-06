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
# Smart Spam Filter (keeps your original mapping)
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
        if not url:
            return ""
        if not url.startswith("http"):
            url = "https://" + url
        headers = {"User-Agent": "Mozilla/5.0 (compatible; OutreachAgent/1.0)"}
        r = requests.get(url, timeout=20, headers=headers)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        # limit to first 4000 chars to avoid huge payloads
        return text[:4000]
    except Exception:
        # keep messages generic to avoid leaking internal detail
        return ""

# -------------------------
# Extract JSON (safe)
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
# Safe API call wrapper (retries + backoff)
# -------------------------
def safe_api_call(func, *args, retries=3, backoff=2, **kwargs):
    for attempt in range(1, retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception:
            if attempt == retries:
                return None
            wait = backoff * attempt + random.random()
            time.sleep(wait)
    return None

# -------------------------
# AI Insights (Groq) - returns text (raw)
# -------------------------
def groq_ai_generate_insights(url, text):
    if not GROQ_API_KEY:
        return ""
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
        r = requests.post(API_URL, headers=headers, json=body, timeout=30)
        r.raise_for_status()
        resp = r.json()
        return resp["choices"][0]["message"]["content"]
    except Exception:
        return ""

# -------------------------
# AI Email Generator (Groq) for pitch types
# -------------------------
def groq_ai_generate_email(url, text, pitch_type, insights):
    if not GROQ_API_KEY:
        return ""
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    company_name = insights.get("company_name", "This Company") if insights else "This Company"
    industry = insights.get("industry", "your industry") if insights else "your industry"
    main_products = insights.get("main_products", []) if insights else []
    ideal_customers = insights.get("ideal_customers", []) if insights else []
    ideal_audience = insights.get("ideal_audience", []) if insights else []
    countries = ", ".join(insights.get("countries_of_operation", [])) if insights else ""

    products_text = ", ".join(main_products) if main_products else "your services/products"
    customers_bullets = "\n".join(ideal_customers) if ideal_customers else "Your best-fit customers"
    audience_bullets = "\n".join(ideal_audience) if ideal_audience else "Your target audience"

    if pitch_type.lower() == "professional":
        prompt = f"""
Return ONLY the below email:

Subject: {company_name}

Hi [First Name],

I noticed {company_name} is doing excellent work in {industry}, offering: {products_text}, across {countries}.  
We help teams like yours connect faster with the decision-makers who matter most:

• Ideal Customers:

{customers_bullets}

• Ideal Audience:

{audience_bullets}

Would you like a short sample to see how we can help you engage these key contacts? It’s completely optional.

Regards,  
Ranjith
"""
    elif pitch_type.lower() == "results":
        prompt = f"""
Return ONLY the below email:

Subject: {company_name}

Hello [First Name],

Companies in {industry} offering {products_text} using our database have seen measurable improvements connecting with the decision-makers who matter:

• Ideal Customers:

{customers_bullets}

• Ideal Audience:

{audience_bullets}

I’d be happy to share a tailored example for {company_name}.

Regards,  
Ranjith
"""
    elif pitch_type.lower() == "data":
        prompt = f"""
Return ONLY the below email:

Subject: {company_name}

Hi [First Name],

Our curated database ensures you reach only verified decision-makers relevant to {industry} and all its offerings: {products_text}.

• Ideal Customers:

{customers_bullets}

• Ideal Audience:

{audience_bullets}

Would you like a short sample to see the quality for yourself?

Thanks,  
Ranjith
"""
    elif pitch_type.lower() == "linkedin":
        prompt = f"""
Return ONLY the below short LinkedIn pitch:

Hi [First Name],

I noticed {company_name} excels in {industry}, offering: {products_text}.  

We help teams connect with:  
• Ideal Customers: {', '.join(ideal_customers) if ideal_customers else 'Your best-fit customers'}  
• Ideal Audience: {', '.join(ideal_audience) if ideal_audience else 'Your target audience'}  

Would you like a quick example of how we can help?

— Ranjith
"""
    else:
        return "Invalid pitch type"

    body = {"model": MODEL_NAME, "messages": [{"role": "user", "content": prompt}], "temperature": 0.55}
    try:
        r = requests.post(API_URL, headers=headers, json=body, timeout=30)
        r.raise_for_status()
        resp = r.json()
        email = resp["choices"][0]["message"]["content"]
        return smart_filter(email)
    except Exception:
        return ""

# -------------------------
# Email parser & formatting (unchanged)
# -------------------------
def parse_email(content):
    subject = ""
    body = ""
    if not content:
        return subject, body
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.lower().startswith("subject:"):
            subject = line.split(":", 1)[1].strip()
            body = "\n".join(lines[i+1:]).strip()
            break
    return subject, body

def format_pitch_markdown(subject, body):
    formatted = f"**Subject:** {subject}\n\n"
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("• Ideal Customers:") or line.startswith("• Ideal Audience:"):
            formatted += f"**{line}**\n\n"
            i += 1
            while i < len(lines) and lines[i].strip() and not lines[i].startswith("• Ideal"):
                formatted += f"{lines[i].strip()}\n\n"
                i += 1
            continue
        elif line:
            formatted += f"{line}\n\n"
        i += 1
    return formatted

# -------------------------
# Bulk analysis (with safe session handling and manual jump)
# -------------------------
def analyze_bulk():
    file = st.file_uploader("Upload CSV or Excel with 'Website' column", type=["csv", "xlsx", "xls"])
    if file is None:
        return

    # Use hash of file contents to detect new upload instead of storing PII (safer)
    try:
        file_bytes = file.getvalue()
        file_hash = hashlib.md5(file_bytes).hexdigest()
    except Exception:
        st.error("Unable to read uploaded file. Please try again.")
        return

    # Initialize only an integer index and last_file_hash in session_state (safe)
    if "bulk_index" not in st.session_state:
        st.session_state.bulk_index = 0
    if "last_file_hash" not in st.session_state:
        st.session_state.last_file_hash = ""

    # Reset index when new file uploaded (checked via hash)
    if st.session_state.last_file_hash != file_hash:
        st.session_state.bulk_index = 0
        st.session_state.last_file_hash = file_hash

    # Load dataframe (no storing of the df in session_state)
    file_name = file.name.lower()
    try:
        if file_name.endswith(".csv"):
            try:
                df = pd.read_csv(file, encoding="utf-8")
            except UnicodeDecodeError:
                df = pd.read_csv(file, encoding="latin1", errors="ignore")
        else:
            df = pd.read_excel(file, engine="openpyxl")
    except Exception:
        st.error("Failed to parse file. Make sure it is a valid CSV/XLSX and contains a 'Website' column.")
        return

    if "Website" not in df.columns:
        st.error("CSV/Excel must contain 'Website' column")
        return

    total_rows = len(df)

    # Manual jump input — user's requested feature
    manual_index = st.number_input(
        f"Enter row number to continue (1 - {total_rows})",
        min_value=1, max_value=total_rows,
        value=st.session_state.bulk_index + 1
    )

    if st.button("Jump to Row ➜"):
        st.session_state.bulk_index = int(manual_index) - 1
        st.rerun()

    index = st.session_state.bulk_index
    if index >= total_rows:
        st.success("🎉 All URLs processed!")
        return

    # Progress indicator
    progress_placeholder = st.empty()
    progress = int((index / max(total_rows, 1)) * 100)
    progress_placeholder.progress(progress)

    # Read only the current row (do NOT store it)
    try:
        url = df.loc[index, "Website"]
    except Exception:
        st.error("Invalid website value at selected row. Skipping to next.")
        if st.button("Skip this row ➜"):
            st.session_state.bulk_index += 1
            st.rerun()
        return

    st.info(f"Processing row {index+1}/{total_rows} → {url}")

    # Display contact details briefly (NOT saved into session_state)
    first_name = df.loc[index].get("First Name", "N/A")
    last_name = df.loc[index].get("Last Name", "N/A")
    company_name_csv = df.loc[index].get("Company Name", "N/A")
    email = df.loc[index].get("Email", "N/A")

    st.subheader("📌 Contact Details")
    st.write(f"**First Name:** {first_name}")
    st.write(f"**Last Name:** {last_name}")
    st.write(f"**Company Name:** {company_name_csv}")
    st.write(f"**Email:** {email}")

    # Scrape and call AI (using safe_api_call wrapper)
    with st.spinner("Scraping website and generating insights..."):
        scraped = scrape_website(str(url))
        insights_raw = safe_api_call(groq_ai_generate_insights, url, scraped)
    insights = extract_json(insights_raw) or {}

    st.subheader("📌 Company Insights")
    if insights:
        st.json(insights)
    else:
        st.info("No structured insights found for this page.")

    if insights.get("ideal_audience"):
        st.markdown("### 🎯 Ideal Audience")
        for a in insights["ideal_audience"]:
            st.write(f"- {a}")

    if insights.get("countries_of_operation"):
        st.markdown("### 🌍 Countries of Operation")
        for c in insights["countries_of_operation"]:
            st.write(f"- {c}")

    pitch_types = ["Professional", "Results", "Data", "LinkedIn"]

    # Generate each pitch (use safe_api_call)
    for pt in pitch_types:
        with st.spinner(f"Generating {pt} pitch..."):
            email_content = safe_api_call(groq_ai_generate_email, url, scraped, pt, insights)
        if not email_content:
            st.warning(f"{pt} pitch not available.")
            continue

        personalized_email = str(email_content).replace("[First Name]", str(first_name))

        if pt.lower() == "linkedin":
            st.subheader("LinkedIn Pitch")
            st.markdown(personalized_email)
        else:
            subject, body = parse_email(personalized_email)

            # SUBJECT OVERRIDE: subject should be only the Company Name from CSV when available
            if company_name_csv and str(company_name_csv).strip() not in ["N/A", "nan", ""]:
                subject = str(company_name_csv).strip()

            st.subheader(f"{pt} Pitch")
            st.markdown(format_pitch_markdown(subject, body))

    # Navigation controls
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("Next ➜"):
            st.session_state.bulk_index += 1
            st.rerun()
    with col2:
        if st.button("Skip ➜"):
            st.session_state.bulk_index += 1
            st.rerun()
    with col3:
        if st.button("Reset to First Row"):
            st.session_state.bulk_index = 0
            st.rerun()

    # Update progress bar after potential actions
    progress_placeholder.progress(int(((st.session_state.bulk_index) / max(total_rows, 1)) * 100))

# -------------------------
# Single URL mode (unchanged behavior; safe handling added)
# -------------------------
def analyze_single():
    url = st.text_input("Enter Website URL")
    if st.button("Analyze Website"):
        if not url:
            st.error("Please enter a website URL.")
            return

        with st.spinner("Scraping and generating insights..."):
            scraped = scrape_website(url)
            insights_raw = safe_api_call(groq_ai_generate_insights, url, scraped)
        insights = extract_json(insights_raw)
        if insights is None:
            st.error("⚠️ No usable insights found")
            return

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

        pitch_types = ["Professional", "Results", "Data", "LinkedIn"]

        for pt in pitch_types:
            with st.spinner(f"Generating {pt} pitch..."):
                email_content = safe_api_call(groq_ai_generate_email, url, scraped, pt, insights)

            if pt.lower() == "linkedin":
                st.subheader("LinkedIn Pitch")
                st.markdown(email_content if email_content else "N/A")
            else:
                subject, body = parse_email(email_content if email_content else "")
                st.subheader(f"{pt} Pitch")
                st.markdown(format_pitch_markdown(subject, body))

# -------------------------
# MAIN UI
# -------------------------
st.title("🌐 Website Outreach AI Agent (Groq) — Safe Bulk Mode")
mode = st.radio("Select Mode", ["Single URL", "Bulk CSV Upload"])

if mode == "Single URL":
    analyze_single()
else:
    analyze_bulk()
