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
API_KEY = "YOUR_GROQ_API_KEY_HERE"
API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"

# --------------------------------------
# FUNCTIONS
# --------------------------------------
def scrape_text(url):
    try:
        response = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.text, "html.parser")
        text = " ".join(soup.stripped_strings)
        return re.sub(r"\s+", " ", text)
    except:
        return ""

def generate_insights(text, url):
    prompt = f"""
    Extract company insights from the content below.
    If a field is missing, return [] or "".

    WEBSITE: {url}

    CONTENT:
    {text}

    Output JSON exactly as:

    {{
    "company_name":"",
    "company_summary":"",
    "main_products":[],
    "ideal_customers":[],
    "ideal_audience":[],
    "industry":"",
    "countries_of_operation":[]
    }}
    """

    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {"model": MODEL, "messages": [{"role": "user", "content": prompt}]}

    try:
        response = requests.post(API_URL, headers=headers, json=payload).json()
        content = response["choices"][0]["message"]["content"]
        return json.loads(content)
    except:
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
st.write("Upload a CSV with a column named **Website**")

uploaded_file = st.file_uploader("Upload CSV", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)

    if "Website" not in df.columns:
        st.error("❌ The CSV must contain a column named 'Website'")
        st.stop()

    st.success(f"📄 Loaded {len(df)} websites.")

    if st.button("Start Processing"):
        progress = st.progress(0)
        results = []
        output_file = "company_insights_output.csv"

        # Load previously saved results to resume (safety)
        if os.path.exists(output_file):
            results = pd.read_csv(output_file).to_dict(orient="records")

        start_index = len(results)

        status_log = st.empty()

        for i in range(start_index, len(df)):
            url = df.iloc[i]["Website"]
            status_log.write(f"🔍 Processing {i+1}/{len(df)} → {url}")

            # STEP 1: Scrape website
            text = scrape_text(url)

            # STEP 2: Generate AI insights
            insights = generate_insights(text, url)
            insights["Website"] = url

            results.append(insights)

            # Save continuously so no data lost if error
            pd.DataFrame(results).to_csv(output_file, index=False)

            # Update progress bar
            progress.progress((i+1) / len(df))

            # Delay 30 seconds per website
            status_log.write(f"⏳ Waiting 30 sec before next website...")
            time.sleep(30)

        st.success("🎯 All websites processed successfully!")
        st.write("Download your result below 👇")
        
        st.download_button(
            label="📥 Download Output CSV",
            data=pd.DataFrame(results).to_csv(index=False),
            file_name="company_insights_output.csv",
            mime="text/csv"
        )
