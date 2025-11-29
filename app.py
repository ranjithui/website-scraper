import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import io
import os

# ---------------------------------------
# STREAMLIT UI SETUP
# ---------------------------------------
st.set_page_config(page_title="Website Outreach Agent", layout="wide")
st.title("🤖 Groq Llama-3 70B Outreach Agent")
st.write("Provide a company website and get insights + outreach messaging.")

# Sidebar setup
st.sidebar.header("Groq API Settings")

# 1️⃣ Load API Key from Streamlit Secrets (for deployment)
API_KEY = st.secrets.get("GROQ_API_KEY", "")

# 2️⃣ Optional: Allow override for local testing
api_key_input = st.sidebar.text_input("Enter Groq API Key (optional override)", type="password")
if api_key_input:
    API_KEY = api_key_input.strip()

# Validate Key
if not API_KEY:
    st.sidebar.error("❌ API Key missing! Add it in Streamlit Secrets or type above.")
else:
    st.sidebar.success("🔐 API Key Loaded")

MODEL = "llama3-70b-8192"

# Sidebar Mode Selector
mode = st.sidebar.radio("Choose Mode", ["Single URL Analysis", "Bulk CSV Upload"])

# ---------------------------------------
# FUNCTION: Scrape Website (Simple)
# ---------------------------------------
def scrape_website(url):
    try:
        if not url.startswith("http"):
            url = "https://" + url

        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        title = soup.title.string if soup.title else "No title found"
        paragraphs = " ".join([p.get_text() for p in soup.find_all("p")])[:3000]

        return f"Title: {title}\n\nContent: {paragraphs}"
    except:
        return "Unable to scrape content."


# ---------------------------------------
# FUNCTION: Analyze Using Groq LLM
# ---------------------------------------
def analyze_content_groq(scraped_content, url):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    prompt = f"""
    You are a B2B sales outreach expert.
    Analyze the following website content and produce:

    1️⃣ Company Summary  
    2️⃣ What they likely sell / services  
    3️⃣ Target customer types  
    4️⃣ 1 Outreach Email Pitch tailored to their business
       - Short
       - No exaggeration
       - Direct value proposition

    Website: {url}
    Content:
    {scraped_content}
    """

    data = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}]
        }

    try:
        res = requests.post("https://api.groq.com/openai/v1/chat/completions",
                            headers=headers, json=data)
        result = res.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Groq API Error: {e}"


# ---------------------------------------
# MODE 1: Single URL
# ---------------------------------------
if mode == "Single URL Analysis":
    url = st.text_input("Enter Website URL (example: www.example.com)")

    if st.button("Analyze"):
        if not API_KEY:
            st.error("Please provide an API Key!")
        elif url:
            scraped = scrape_website(url)
            result = analyze_content_groq(scraped, url)
            st.subheader("📌 Outreach Report")
            st.write(result)


# ---------------------------------------
# MODE 2: Bulk CSV Upload
# ---------------------------------------
else:
    st.write("Upload CSV file containing URL column")

    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])

    if uploaded_file and API_KEY:
        df = pd.read_csv(uploaded_file)

        # Detect column with URLs
        url_column = df.columns[0]

        st.write(f"Detected URL column: **{url_column}**")

        if st.button("Start Bulk Outreach"):
            results = []

            with st.spinner("Processing all websites... Please wait ⏳"):
                for url in df[url_column]:
                    scraped = scrape_website(str(url))
                    reply = analyze_content_groq(scraped, str(url))
                    results.append(reply)

            df["Outreach Pitch"] = results

            st.success("Bulk Processing Completed ✔")
            st.dataframe(df)

            # Download button
            csv = df.to_csv(index=False).encode()
            st.download_button(
                "📥 Download Outreach Results CSV",
                csv,
                "outreach_results.csv",
                "text/csv"
            )
