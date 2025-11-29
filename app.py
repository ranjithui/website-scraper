import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json

st.set_page_config(page_title="Website Outreach Agent", layout="wide")

# Load API key from Streamlit secrets
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]

API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL_NAME = "llama3-8b-8192"

def scrape_website(url):
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        texts = soup.get_text(separator=" ", strip=True)
        return texts[:4000]  # limit tokens
    except:
        return ""

def groq_ai_analyze(url, text):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""
You are a B2B sales outreach AI Agent.
Analyze this website and give:

1️⃣ What the company does (2 lines)
2️⃣ The ideal targets (3 bullet points)
3️⃣ Best outreach angle (2 bullet points)
4️⃣ Suggested email subject line (1 line)

Website: {url}

Scraped Content: {text}
"""

    body = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        r = requests.post(API_URL, headers=headers, json=body)
        response = r.json()

        if "choices" not in response:
            return f"❌ Groq API Unexpected Response: {json.dumps(response, indent=2)}"

        return response["choices"][0]["message"]["content"]

    except Exception as e:
        return f"⚠️ API Error: {e}"

def analyze_single_url():
    url = st.text_input("Enter Website URL:")
    if st.button("Analyze"):
        if url:
            text = scrape_website(url)
            result = groq_ai_analyze(url, text)
            st.subheader("Analysis Result")
            st.write(result)

def analyze_bulk():
    file = st.file_uploader("Upload CSV with 'url' column", type=["csv"])

    if file is not None:
        df = pd.read_csv(file)

        if "url" not in df.columns:
            st.error("CSV must contain a 'url' column")
            return

        if st.button("Run Bulk Analysis"):
            results = []
            progress = st.progress(0)

            for i, row in df.iterrows():
                url = row["url"]
                text = scrape_website(url)
                result = groq_ai_analyze(url, text)
                results.append({"url": url, "analysis": result})

                progress.progress((i + 1) / len(df))

            result_df = pd.DataFrame(results)
            st.success("Bulk Analysis Completed!")
            st.dataframe(result_df)

            csv = result_df.to_csv(index=False).encode('utf-8')
            st.download_button("Download Results CSV", csv, "results.csv", "text/csv")

# UI Layout
st.title("🌐 Website Outreach AI Agent (Groq)")

mode = st.radio("Select Mode", ["Single URL", "Bulk CSV Upload"])

if mode == "Single URL":
    analyze_single_url()
else:
    analyze_bulk()
