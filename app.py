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
        if "ideal_customers" not in data:
            data["ideal_customers"] = []
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
    except Exception as e:
        return ""

# -------------------------
# Call AI for Emails Only
# -------------------------
def groq_ai_generate_email(url, text, tone, insights):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    company_name = insights.get("company_name", "This Company")
    company_summary = insights.get("company_summary", "A growing organization")
    main_products = ", ".join(insights.get("main_products", []))
    industry = insights.get("industry", "your industry")
    ideal_customers = insights.get("ideal_customers", [])
    # Convert ideal customers into bullets
    customers_bullets = "\n• ".join(ideal_customers) if ideal_customers else "Your ideal clients"

    if "professional" in tone.lower():
        prompt = f"""
You are a B2B sales outreach expert.

Analyze the following company and generate an outreach email in EXACT format.

Company Name: {company_name}
Industry: {industry}
Summary: {company_summary}
Main Products/Services: {main_products}
Ideal Customers: {customers_bullets}

Return ONLY the email in this format:

Subject: Enhance Your Outreach with Targeted Contacts at {company_name}

Hello [First Name],

I noticed {company_name} is focusing on {main_products}.  
We provide targeted email lists to help you connect with:
• {customers_bullets}

If this aligns with your outreach strategy, I’d be happy to share more details along with a small sample for your review.

Looking forward to your thoughts,  
Ranjith
"""
    else:
        prompt = f"""
You are a B2B sales outreach expert.

Analyze the following company and generate an outreach email in EXACT format.

Company Name: {company_name}
Industry: {industry}
Summary: {company_summary}
Main Products/Services: {main_products}
Ideal Customers: {customers_bullets}

Return ONLY the email in this format:

Subject: Connect with Key Decision-Makers at {company_name}

Hi [First Name],  

I came across {company_name} and noticed you’re doing exciting work in {industry}.  
We provide targeted email lists to help you reach:
• {customers_bullets}

If you're open to it, I’d love to share more details — plus a small sample list so you can see the fit firsthand.

What do you say — should we give it a quick try? 😊

Cheers,  
Ranjith 🚀
"""

    body = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.55
    }

    try:
        r = requests.post(API_URL, headers=headers, json=body)
        res = r.json()
        return res["choices"][0]["message"]["content"]
    except Exception as e:
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

            company_summary = insights["company_summary"] if insights else "A growing organization"

            prof_email = groq_ai_generate_email(url, scraped, "Professional Corporate Tone", insights)
            friendly_email = groq_ai_generate_email(url, scraped, "Friendly Conversational Tone", insights)

            sp, bp = parse_email(prof_email)
            sf, bf_body = parse_email(friendly_email)

            st.subheader("📌 Company Insights")
            if insights:
                st.json(insights)
            else:
                st.text("No insights found")

            st.subheader("1️⃣ Professional Corporate Tone")
            st.text_area("Professional", f"Subject: {sp}\n\n{bp}", height=220)

            st.subheader("2️⃣ Friendly Conversational Tone")
            st.text_area("Friendly", f"Subject: {sf}\n\n{bf_body}", height=220)

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
                sf, bf_body = parse_email(f)

                results.append({
                    "url": url,
                    "company_summary": summary,
                    "professional_subject": sp,
                    "professional_body": bp,
                    "friendly_subject": sf,
                    "friendly_body": bf_body
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
