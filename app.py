import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import json
import time
import re
import os

# --------------------------------------
# CONFIG
# --------------------------------------
st.set_page_config(page_title="Company Insights AI", layout="wide")

# Load Key from Streamlit Secrets
API_KEY = st.secrets["GROQ_API_KEY"]

API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"


# --------------------------------------
# FUNCTIONS
# --------------------------------------

def scrape_text(url):
    """Scrape website text + metadata + JSON-LD"""

    try:
        response = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.text, "html.parser")

        text = " ".join(soup.stripped_strings)

        # Meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            text += " " + meta_desc["content"]

        # JSON-LD Structured data
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                schema = json.loads(script.text.strip())
                text += " " + json.dumps(schema)
            except:
                pass

        return re.sub(r"\s+", " ", text[:20000])

    except Exception as e:
        print(f"[SCRAPE ERROR] {url}: {e}")
        return ""


def generate_insights(text, url, attempts=3):
    """Call Groq API and enforce valid JSON response, with retry."""

    prompt = f"""
    Analyze the website content below and extract structured business insights.

    WEBSITE: {url}

    CONTENT:
    {text}

    Return ONLY valid JSON formatted EXACTLY like this structure:

    {{
        "company_name": "",
        "company_summary": "",
        "main_products": [],
        "ideal_customers": [],
        "ideal_audience": [],
        "industry": "",
        "countries_of_operation": []
    }}
    """

    for attempt in range(attempts):

        try:
            headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

            payload = {
                "model": MODEL,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "user", "content": prompt}]
            }

            response = requests.post(API_URL, headers=headers, json=payload).json()

            content = response["choices"][0]["message"]["content"]

            return json.loads(content)

        except Exception as e:
            print(f"[AI ERROR] Attempt {attempt+1} for {url}: {e}")
            time.sleep(3)

    return {
        "company_name": "",
        "company_summary": "",
        "main_products": [],
        "ideal_customers": [],
        "ideal_audience": [],
        "industry": "",
        "countries_of_operation": []
    }


# --------------------------------------
# UI
# --------------------------------------

st.title("📊 Company Insights AI Extractor")
st.write("Upload a CSV containing a column named **Website** to begin.")

uploaded_file = st.file_uploader("Upload CSV", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    if "Website" not in df.columns:
        st.error("❌ The CSV must contain a column named 'Website'")
        st.stop()

    st.success(f"📄 Loaded {len(df)} websites.")

    if st.button("🚀 Start Processing"):
        progress = st.progress(0)
        results = []
        output_file = "company_insights_output.csv"

        # Resume mode
        if os.path.exists(output_file):
            results = pd.read_csv(output_file).to_dict(orient="records")

        start_index = len(results)
        status_log = st.empty()

        for i in range(start_index, len(df)):
            url = str(df.iloc[i]["Website"]).strip()
            status_log.write(f"🔍 Processing {i+1}/{len(df)} → {url}")

            # Scrape content
            text = scrape_text(url)

            # AI extraction
            insights = generate_insights(text, url)
            insights["Website"] = url

            results.append(insights)

            # Save continuously
            pd.DataFrame(results).to_csv(output_file, index=False)

            progress.progress((i+1) / len(df))

            status_log.write(f"⏳ Waiting 5 sec before next website...")
            time.sleep(5)

        st.success("🎉 Completed! Download your results below.")

        st.download_button(
            label="📥 Download Output CSV",
            data=pd.DataFrame(results).to_csv(index=False),
            file_name="company_insights_output.csv",
            mime="text/csv"
        )
