import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import json
import time

st.set_page_config(page_title="Bulk Website AI Insights – Live Scraping UI", layout="wide")

# -------------------------------------------------------
# CONFIG
# -------------------------------------------------------
GROQ_KEY = st.secrets["GROQ_API_KEY"]
API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"

# -------------------------------------------------------
# SCRAPER WITH MULTI-URL FALLBACK
# -------------------------------------------------------
def try_fetch(url):
    try:
        r = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            return r.text
    except:
        pass
    return None


def scrape_site(raw_url):
    raw_url = str(raw_url).strip()

    base = raw_url.replace("https://", "").replace("http://", "").replace("www.", "")

    attempts = [
        f"https://{base}",
        f"http://{base}",
        f"https://www.{base}",
        f"http://www.{base}",
    ]

    for link in attempts:
        html = try_fetch(link)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(" ", strip=True)
            return text[:4000], link, attempts

    return "SCRAPE_ERROR: Could not fetch website", None, attempts

# -------------------------------------------------------
# AI INSIGHTS USING STRICT JSON OUTPUT
# -------------------------------------------------------
def get_ai_insights(url, scraped_text):
    prompt = f"""
Extract ONLY B2B insights (ignore B2C except HNWI/UHNWI).

Return ONLY clean JSON.

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

    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}

    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.15
    }

    try:
        r = requests.post(API_URL, json=body, headers=headers, timeout=40)
        raw = r.json()["choices"][0]["message"]["content"]

        start = raw.find("{")
        end = raw.rfind("}")

        if start == -1 or end == -1:
            return {"error": "AI returned invalid JSON"}

        return json.loads(raw[start:end + 1])

    except Exception as e:
        return {"error": str(e)}

# -------------------------------------------------------
# PROCESSOR (SHOWS LIVE UPDATES IN UI)
# -------------------------------------------------------
def process_csv(df, website_column, live_box):
    results = []

    for idx, row in df.iterrows():
        website = row[website_column]

        live_box.markdown(f"## 🔍 Processing {idx+1}/{len(df)} – **{website}**")

        scraped_text, final_url, attempts = scrape_site(website)

        # Show fallback attempts
        with st.expander("🌐 URL Attempts", expanded=False):
            st.write(attempts)

        if final_url:
            live_box.success(f"✅ Working URL: **{final_url}**")
        else:
            live_box.error("❌ No valid URL found, using raw domain.")

        # Show scraped data live
        live_box.write("### 📄 Scraped Content:")
        live_box.write(scraped_text[:600] + "...")

        # AI extraction
        ai_data = get_ai_insights(final_url or website, scraped_text)

        live_box.write("### 🤖 AI Insights JSON:")
        live_box.json(ai_data)

        combined = {**row.to_dict(), **ai_data}
        results.append(combined)

        time.sleep(1.5)

    return pd.DataFrame(results)

# -------------------------------------------------------
# UI
# -------------------------------------------------------
st.title("🌍 Live Website Scraper + AI B2B Insights")

file = st.file_uploader("📤 Upload CSV (must contain Website column)", type=["csv"])

if file:
    df = pd.read_csv(file)
    st.write("### 📁 Preview:")
    st.dataframe(df.head())

    # Auto-detect Website column
    possible_cols = ["website", "url", "domain"]
    auto_col = next((c for c in df.columns if c.lower() in possible_cols), df.columns[0])

    website_column = st.selectbox("Select Website Column", df.columns, index=list(df.columns).index(auto_col))

    live_box = st.empty()

    if st.button("🚀 Start Processing", use_container_width=True):
        with st.spinner("Scraping websites + generating AI insights..."):
            final_df = process_csv(df, website_column, live_box)

        st.success("🎉 Processing Complete!")
        st.dataframe(final_df)

        st.download_button(
            "📥 Download Results CSV",
            data=final_df.to_csv(index=False).encode("utf-8"),
            file_name="ai_website_insights.csv",
            mime="text/csv",
            use_container_width=True,
        )
