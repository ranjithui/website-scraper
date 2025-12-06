import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import re
import tempfile

st.set_page_config(page_title="Website Outreach AI Agent", layout="wide")

# -------------------------
# Load API key
# -------------------------
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
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
    for pattern, replacement in spam_words_map.items():
        text = re.sub(pattern, replacement, text)
    return text

# -------------------------
# Website Scraping (cached)
# -------------------------
@st.cache_data(show_spinner=False)
def cached_scrape(url):
    try:
        if not url.startswith("http"):
            url = "https://" + url
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        return text[:4000]
    except Exception as e:
        return ""

# -------------------------
# Extract JSON from AI response
# -------------------------
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

# -------------------------
# AI Insights (cached)
# -------------------------
@st.cache_data(show_spinner=False)
def cached_ai_insights(url, scraped_text):
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
Website Content: {scraped_text}
"""
    body = {"model": MODEL_NAME, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3}
    try:
        r = requests.post(API_URL, headers=headers, json=body)
        raw_json = r.json()["choices"][0]["message"]["content"]
        return extract_json(raw_json)
    except:
        return None

# -------------------------
# AI Email Generator (cached)
# -------------------------
@st.cache_data(show_spinner=False)
def cached_ai_email(url, pitch_type, insights, first_name):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    company_name = insights.get("company_name", "This Company")
    industry = insights.get("industry", "your industry")
    main_products = insights.get("main_products", [])
    ideal_customers = insights.get("ideal_customers", [])
    ideal_audience = insights.get("ideal_audience", [])
    countries = ", ".join(insights.get("countries_of_operation", []))

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
        r = requests.post(API_URL, headers=headers, json=body)
        email = r.json()["choices"][0]["message"]["content"]
        return smart_filter(email.replace("[First Name]", str(first_name)))
    except:
        return ""

# -------------------------
# Email Parser
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
# Format Pitch for Markdown
# -------------------------
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
# BULK UPLOAD MODE
# -------------------------
# -------------------------
# BULK UPLOAD MODE (patched)
# -------------------------
def analyze_bulk():
    file = st.file_uploader("Upload CSV or Excel with 'Website' column", type=["csv", "xlsx", "xls"])
    if file is None:
        return

    # Initialize session state for bulk processing
    if "last_uploaded_file" not in st.session_state or st.session_state.last_uploaded_file != file.name:
        st.session_state.bulk_index = 0
        st.session_state.bulk_results = []
        st.session_state.last_uploaded_file = file.name

    # Read file
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

    index = st.session_state.bulk_index
    total_rows = len(df)

    if index >= total_rows:
        st.success("🎉 All URLs processed! Download your data below 👇")
        # Export final results
        if st.session_state.bulk_results:
            results_df = pd.DataFrame(st.session_state.bulk_results)
            
            # CSV Download
            csv = results_df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download Full Report (CSV)", csv, "outreach_analysis.csv", "text/csv")

            # Excel Download
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                results_df.to_excel(tmp.name, index=False, engine="openpyxl")
                with open(tmp.name, "rb") as f:
                    st.download_button("⬇️ Download Full Report (Excel)", f, "outreach_analysis.xlsx",
                                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        return

    # Safely access current row
    current_row = df.iloc[index]
    url = current_row.get("Website", "")
    first_name = current_row.get("First Name", "N/A")
    last_name = current_row.get("Last Name", "N/A")
    company_name_csv = current_row.get("Company Name", "N/A")
    email = current_row.get("Email", "N/A")

    st.subheader(f"Processing {index+1}/{total_rows} → {url}")
    st.write(f"**First Name:** {first_name}")
    st.write(f"**Last Name:** {last_name}")
    st.write(f"**Company Name:** {company_name_csv}")
    st.write(f"**Email:** {email}")

    # Scrape and get AI insights (cached)
    scraped = cached_scrape(url)
    insights = cached_ai_insights(url, scraped)
    st.subheader("📌 Company Insights")
    st.json(insights)

    # Generate pitches
    pitch_types = ["Professional", "Results", "Data", "LinkedIn"]
    pitches = {}
    for pt in pitch_types:
        pitches[pt] = cached_ai_email(url, pt, insights, first_name)
        if pt == "LinkedIn":
            st.subheader("LinkedIn Pitch")
            st.markdown(pitches[pt])
        else:
            subject, body = parse_email(pitches[pt])
            if company_name_csv and str(company_name_csv).strip() and str(company_name_csv) != "N/A" and not pd.isna(company_name_csv):
                subject = str(company_name_csv).strip()
            st.subheader(f"{pt} Pitch")
            st.markdown(format_pitch_markdown(subject, body))

    # Save sanitized results
    st.session_state.bulk_results.append({
        "Website": url,
        "First Name": first_name,
        "Last Name": last_name,
        "Company Name": company_name_csv,
        "Email": email,
        "Insights": json.dumps(insights, ensure_ascii=False),
        "Professional Pitch": pitches["Professional"],
        "Results Pitch": pitches["Results"],
        "Data Pitch": pitches["Data"],
        "LinkedIn Pitch": pitches["LinkedIn"]
    })

    # Move to next row
    if st.button("Next Website ➜"):
        if st.session_state.bulk_index < total_rows - 1:
            st.session_state.bulk_index += 1
        else:
            st.success("🎉 All URLs processed! Download your data above 👆")


# -------------------------
# SINGLE URL MODE
# -------------------------
def analyze_single():
    url = st.text_input("Enter Website URL")
    if st.button("Analyze Website"):
        scraped = cached_scrape(url)
        insights = cached_ai_insights(url, scraped)
        if insights is None:
            st.error("⚠️ No usable insights found")
            return

        st.subheader("📌 Company Insights")
        st.json(insights)

        pitch_types = ["Professional", "Results", "Data", "LinkedIn"]
        for pt in pitch_types:
            email_content = cached_ai_email(url, pt, insights, "FirstName")
            if pt == "LinkedIn":
                st.subheader("LinkedIn Pitch")
                st.markdown(email_content)
            else:
                subject, body = parse_email(email_content)
                st.subheader(f"{pt} Pitch")
                st.markdown(format_pitch_markdown(subject, body))

# -------------------------
# MAIN UI
# -------------------------
st.title("🌐 Website Outreach AI Agent (Groq)")
mode = st.radio("Select Mode", ["Single URL", "Bulk CSV Upload"])

if mode == "Single URL":
    analyze_single()
else:
    analyze_bulk()
