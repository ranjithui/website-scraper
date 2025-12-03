import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json

st.set_page_config(page_title="Website Outreach AI Agent", layout="wide")

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL_NAME = "llama-3.3-70b-versatile"

def normalize_url(val):
    if not isinstance(val, str):
        return ""
    val = val.strip()
    if not val:
        return ""
    if val.startswith("http://") or val.startswith("https://"):
        return val
    return "http://" + val

def scrape_website(url):
    if not url:
        return ""
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        return text[:4000]
    except Exception as e:
        return f"[SCRAPE_FAILED] Could not fetch {url}: {e}"

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
    body = {"model": MODEL_NAME, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3}
    try:
        r = requests.post(API_URL, headers=headers, json=body)
        res = r.json()
        return res["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[AI_ERROR] {e}"

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

def analyze_bulk_row_by_row():
    uploaded = st.file_uploader("Upload CSV with 'Website' column", type=["csv"], key="bulk_upload")
    if uploaded is not None:
        if "bulk_df" not in st.session_state or st.session_state.get("bulk_file_id") != uploaded.name:
            try:
                df = pd.read_csv(uploaded)
            except Exception as e:
                st.error(f"Failed to read CSV: {e}")
                return
            if "Website" not in df.columns and "url" in df.columns:
                df = df.rename(columns={"url": "Website"})
            if "Website" not in df.columns:
                st.error("CSV must contain a 'Website' column")
                return
            st.session_state.bulk_df = df.reset_index(drop=True)
            st.session_state.bulk_idx = 0
            st.session_state.bulk_total = len(df)
            st.session_state.bulk_file_id = uploaded.name
            st.session_state.finished = False
        df = st.session_state.bulk_df
        idx = st.session_state.bulk_idx
        total = st.session_state.bulk_total
        st.sidebar.markdown(f"**Row:** {idx+1} of {total}")
        current_Website = normalize_url(str(df.loc[idx, "Website"]))
        st.subheader(f"Record {idx+1} of {total}")
        st.write(current_Website)
        if st.button("Fetch Current", key=f"fetch_{idx}"):
            if not current_Website:
                st.warning(f"Skipping - Invalid Website")
            else:
                scraped = scrape_website(current_Website)
                if not scraped:
                    st.warning(f"Skipping - No data scraped from {current_Website}")
                else:
                    insights_raw = groq_ai_generate_insights(current_Website, scraped)
                    insights = extract_json(insights_raw)
                    st.subheader("📌 Company Insights")
                    st.json(insights if insights else insights_raw)
        if st.button("Next Website", key=f"next_{idx}"):
            if st.session_state.bulk_idx < st.session_state.bulk_total - 1:
                st.session_state.bulk_idx += 1
                st.experimental_rerun()
            else:
                st.session_state.finished = True
        if st.session_state.get("finished"):
            st.success("All rows completed!")
            if st.button("Restart from first record"):
                st.session_state.bulk_idx = 0
                st.session_state.finished = False
                st.experimental_rerun()

mode = st.radio("Select Mode", ["Single URL", "Bulk CSV Upload"], index=1)
if mode == "Bulk CSV Upload":
    analyze_bulk_row_by_row()
