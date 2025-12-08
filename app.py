import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import json
import time

st.set_page_config(page_title="Bulk Website AI Insights", layout="wide")

# ---------------------------
# CONFIG (Uses Streamlit Secrets)
# ---------------------------
GROQ_KEY = st.secrets["GROQ_API_KEY"]
API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"


# ---------------------------
# Scrape Website
# ---------------------------
def scrape_site(url):
    try:
        if not url.startswith("http"):
            url = "https://" + url

        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(" ", strip=True)
        return text[:4000]  # keep short for model efficiency

    except Exception as e:
        return f"SCRAPE_ERROR: {str(e)}"


# ---------------------------
# Extract ONLY JSON via AI
# ---------------------------
def get_ai_insights(url, scraped_text):
    prompt = f"""
Extract structured company insights from the website content.

Return ONLY a CLEAN VALID JSON. No text outside JSON.

JSON format:

{{
"company_name": "",
"company_summary": "",
"main_products": [],
"ideal_customers": [],
"ideal_audience": [],
"industry": "",
"countries_of_operation": []
}}

Website: {url}
Content: {scraped_text}
"""

    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }

    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2
    }

    try:
        r = requests.post(API_URL, json=body, headers=headers)
        raw = r.json()["choices"][0]["message"]["content"]

        # Extract json strictly
        start = raw.find("{")
        end = raw.rfind("}") + 1

        if start == -1 or end == -1:
            return {"error": "Invalid AI Response"}

        return json.loads(raw[start:end])

    except Exception as e:
        return {"error": str(e)}


# ---------------------------
# Batch Processor
# ---------------------------
def process_csv(df, website_column, live_box):
    results = []

    for i, row in df.iterrows():
        website = row[website_column]

        live_box.markdown(f"### 🔍 Processing {i+1}/{len(df)} — `{website}`")

        scraped = scrape_site(website)
        ai_data = get_ai_insights(website, scraped)

        live_box.write("📌 **Insights:**")
        live_box.json(ai_data)

        combined = {**row.to_dict(), **ai_data}
        results.append(combined)

        time.sleep(20)  # 20 sec delay

    return pd.DataFrame(results)


# ---------------------------
# UI
# ---------------------------
st.title("🌍 Bulk Website → AI Insights Generator")

file = st.file_uploader("📤 Upload CSV (Must Contain 'Website' Column)", type=["csv"])

if file:

    df = pd.read_csv(file)
    st.write("📁 Preview:")
    st.dataframe(df.head())

    # Auto-detect Website column
    auto_col = None
    for c in df.columns:
        if c.lower() in ["website", "url", "domain"]:
            auto_col = c
            break

    website_column = st.selectbox("Select Website Column:", df.columns.tolist(),
                                  index=df.columns.tolist().index(auto_col) if auto_col else 0)

    live_box = st.empty()

    if st.button("🚀 Start Processing"):
        with st.spinner("Running AI + Web Scraping... This may take some time ⏳"):
            final_df = process_csv(df, website_column, live_box)

        st.success("🎉 Processing Complete!")
        st.dataframe(final_df)

        csv_data = final_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            "📥 Download Results CSV",
            data=csv_data,
            file_name="ai_website_insights.csv",
            mime="text/csv"
        )

