import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json

st.set_page_config(page_title="Website Outreach AI Agent", layout="wide")

# Load API key
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL_NAME = "llama-3.3-70b-versatile"

# -------------------------
# Helper: safe URL getter
# -------------------------

def normalize_Website(val):
    if not isinstance(val, str):
        return ""
    val = val.strip()
    if not val:
        return ""
    if val.startswith("http://") or val.startswith("https://"):
        return val
    # try to be helpful and add scheme
    return "http://" + val

# -------------------------
# Scrape Website Content
# -------------------------

def scrape_website(Website):
    if not Website:
        return ""
    try:
        r = requests.get(Website, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        return text[:4000]
    except Exception as e:
        return f"""[SCRAPE_FAILED] Could not fetch {Website}: {e}"""

# -------------------------
# Extract JSON Insights (unchanged)
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
    except Exception:
        return None

# -------------------------
# Call AI for Insights Only
# -------------------------

def groq_ai_generate_insights(Website, text):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""
You are a business analyst. Extract ONLY JSON insights from the website.

Return in this exact JSON format:

{
"company_name": "Company Name",
"company_summary": "2-3 line summary",
"main_products": ["service 1", "service 2", "service 3"],
"ideal_customers": ["ICP1", "ICP2", "ICP3"],
"industry": "best guess industry"
}

Company URL: {Website}
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
        return f"[AI_ERROR] {e}"

# -------------------------
# Call AI for Emails Only
# -------------------------

def groq_ai_generate_email(Website, text, tone, insights):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    company_name = insights.get("company_name", "This Company") if insights else "This Company"
    company_summary = insights.get("company_summary", "A growing organization") if insights else "A growing organization"
    main_products = ", ".join(insights.get("main_products", [])) if insights else ""
    industry = insights.get("industry", "your industry") if insights else "your industry"
    ideal_customers = insights.get("ideal_customers", []) if insights else []
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
        return f"[AI_ERROR] {e}"

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
# Single URL Mode (unchanged)
# -------------------------

def analyze_single_Website():
    Website = st.text_input("Enter Website URL:")

    if st.button("Analyze"):
        if Website:
            scraped = scrape_website(normalize_Website(Website))
            st.subheader("⏳ Processing... Please wait")

            insights_raw = groq_ai_generate_insights(Website, scraped)
            insights = extract_json(insights_raw)

            company_summary = insights["company_summary"] if insights else "A growing organization"

            prof_email = groq_ai_generate_email(Website, scraped, "Professional Corporate Tone", insights)
            friendly_email = groq_ai_generate_email(Website, scraped, "Friendly Conversational Tone", insights)

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
# Bulk CSV Mode - ROW BY ROW
# -------------------------

def analyze_bulk_row_by_row():
    st.info("Upload a CSV with a 'Website' column (falls back to 'Website' column). Processing is manual: press 'Fetch Current' then 'Next Website'.")

    uploaded = st.file_uploader("Upload CSV", type=["csv"] , key="bulk_upload")

    if uploaded is not None:
        if "bulk_df" not in st.session_state or st.session_state.get("bulk_file_id") != uploaded.name:
            # load dataframe and reset index state
            try:
                df = pd.read_csv(uploaded)
            except Exception as e:
                st.error(f"Failed to read CSV: {e}")
                return

            # Normalize column name: prefer 'Website', fallback to 'Website'
            if "Website" not in df.columns and "website" in df.columns:
                df = df.rename(columns={"website": "Website"})
            if "Website" not in df.columns and "Website" in df.columns:
                df = df.rename(columns={"Website": "Website"})

            if "Website" not in df.columns:
                st.error("CSV must contain a 'Website' or 'Website' column")
                return

            st.session_state.bulk_df = df.reset_index(drop=True)
            st.session_state.bulk_idx = 0
            st.session_state.bulk_total = len(st.session_state.bulk_df)
            st.session_state.bulk_file_id = uploaded.name
            st.session_state.finished = False

        df = st.session_state.bulk_df
        idx = st.session_state.bulk_idx
        total = st.session_state.bulk_total

        st.sidebar.markdown(f"**Row:** {idx+1} of {total}")
        current_Website_raw = df.loc[idx, "Website"]
        current_Website = normalize_Website(str(current_Website_raw))

        st.subheader(f"Record {idx+1} of {total}")
        st.write(current_Website)

        col1, col2 = st.columns([1,1])
        with col1:
            if st.button("Fetch Current", key=f"fetch_{idx}"):
                with st.spinner("Scraping + Generating insights & emails (this may take a few seconds)..."):
                    scraped = scrape_website(current_Website)

                    insights_raw = groq_ai_generate_insights(current_Website, scraped)
                    insights = extract_json(insights_raw)

                    prof_email = groq_ai_generate_email(current_Website, scraped, "Professional Corporate Tone", insights)
                    friendly_email = groq_ai_generate_email(current_Website, scraped, "Friendly Conversational Tone", insights)

                    sp, bp = parse_email(prof_email)
                    sf, bf_body = parse_email(friendly_email)

                    st.session_state.last_result = {
                        "Website": current_Website,
                        "insights_raw": insights_raw,
                        "insights": insights,
                        "professional_subject": sp,
                        "professional_body": bp,
                        "friendly_subject": sf,
                        "friendly_body": bf_body
                    }

        with col2:
            if st.button("Next Website", key=f"next_{idx}"):
                # advance index safely
                if st.session_state.bulk_idx < st.session_state.bulk_total - 1:
                    st.session_state.bulk_idx += 1
                    st.experimental_rerun()
                else:
                    st.session_state.finished = True

        # Display last result if available
        if st.session_state.get("last_result"):
            res = st.session_state.last_result
            st.markdown("---")
            st.subheader("📌 Company Insights (latest)")
            if res.get("insights"):
                st.json(res.get("insights"))
            else:
                st.text(res.get("insights_raw") or "No insights found")

            st.subheader("1️⃣ Professional Corporate Tone")
            st.text_area("Professional", f"Subject: {res.get('professional_subject')}\n\n{res.get('professional_body')}", height=220)

            st.subheader("2️⃣ Friendly Conversational Tone")
            st.text_area("Friendly", f"Subject: {res.get('friendly_subject')}\n\n{res.get('friendly_body')}", height=220)

        if st.session_state.get("finished"):
            st.success("All rows completed!")
            if st.button("Restart from first record"):
                st.session_state.bulk_idx = 0
                st.session_state.finished = False
                st.session_state.last_result = None
                st.experimental_rerun()

# -------------------------
# UI Layout
# -------------------------

st.title("🌐 Website Outreach AI Agent (Groq) - Row-by-Row Bulk Mode")

mode = st.radio("Select Mode", ["Single URL", "Bulk CSV Upload"], index=1)

if mode == "Single URL":
    analyze_single_Website()
else:
    analyze_bulk_row_by_row()
