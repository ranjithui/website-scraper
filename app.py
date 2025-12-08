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
st.set_page_config(page_title="📊 Company Insights AI", layout="wide")

# Load key from secrets
API_KEY = st.secrets["GROQ_API_KEY"]
API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"


# --------------------------------------
# SCRAPER (Fixed & Smart)
# --------------------------------------
def scrape_text(url):
    """Scrape visible text + metadata with fallback for HTTPS/WWW."""
    
    if not url.startswith("http"):
        url = "https://" + url

    candidate_urls = [url]

    if "www." not in url:
        candidate_urls.append(url.replace("https://", "https://www."))

    candidate_urls.append(url.replace("https://", "http://"))

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }

    for attempt_url in candidate_urls:
        try:
            response = requests.get(attempt_url, timeout=15, headers=headers)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")

                text = soup.get_text(" ", strip=True)

                # Meta description
                meta = soup.find("meta", attrs={"name": "description"})
                if meta and meta.get("content"):
                    text += " " + meta["content"]

                # JSON LD
                for script in soup.find_all("script", type="application/ld+json"):
                    try:
                        text += " " + script.text
                    except:
                        pass

                cleaned = re.sub(r"\s+", " ", text)
                return cleaned[:15000]
        except:
            continue

    return ""


# --------------------------------------
# AI CALL (Failsafe JSON)
# --------------------------------------
def generate_insights(text, url):
    if len(text.strip()) < 50:
        text = "NO SCRAPED CONTENT — infer from company name & domain context."

    prompt = f"""
    Extract business insights based on the content below.

    URL: {url}

    WEBSITE TEXT:
    {text}

    Return ONLY valid JSON in this exact schema:

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

    try:
        response = requests.post(
            API_URL,
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={
                "model": MODEL,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "user", "content": prompt}]
            }
        )

        return json.loads(response.json()["choices"][0]["message"]["content"])

    except Exception as e:
        print("AI ERROR:", e)

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
st.write("Upload a CSV with a column named **Website** to start.")


uploaded_file = st.file_uploader("Upload CSV", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    if "Website" not in df.columns:
        st.error("❌ CSV must contain a column named 'Website'.")
        st.stop()

    st.success(f"📁 Loaded {len(df)} websites.")

    if st.button("🚀 Start Processing"):

        output_file = "company_insights_output.csv"
        results = []

        # If already processed earlier → resume mode
        if os.path.exists(output_file):
            results = pd.read_csv(output_file).to_dict(orient="records")

        progress = st.progress(0)
        status = st.empty()

        start_index = len(results)

        for i in range(start_index, len(df)):
            url = str(df.iloc[i]["Website"]).strip()

            status.write(f"🔍 Scraping {i+1}/{len(df)} — {url}")

            scraped_text = scrape_text(url)
            insights = generate_insights(scraped_text, url)
            insights["Website"] = url

            results.append(insights)

            pd.DataFrame(results).to_csv(output_file, index=False)

            progress.progress((i + 1) / len(df))

            status.write(f"⏳ Waiting 5 seconds before next URL...")
            time.sleep(5)

        st.success("🎉 All websites processed!")

        st.download_button(
            label="📥 Download Results CSV",
            data=pd.DataFrame(results).to_csv(index=False),
            file_name="company_insights_output.csv",
            mime="text/csv"
        )
