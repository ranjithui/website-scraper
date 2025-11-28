"""
Two-Mode Website Outreach Agent (Streamlit)
Modes:
 - Single URL analyze (fast)
 - Bulk CSV upload (column 'url' or single column of URLs)

Provider support:
 - OpenAI (api.openai.com) or Groq (api.groq.com/openai)
User provides API key and selects provider.

Usage:
  pip install streamlit requests beautifulsoup4 python-dotenv pandas
  streamlit run outreach_two_mode.py
"""

import os
import io
import time
import json
import requests
import pandas as pd
from bs4 import BeautifulSoup
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Outreach Agent — Single & Bulk", layout="wide")

st.title("📬 Outreach Agent — Single URL & Bulk CSV")

st.markdown("""
This app analyzes a company website and generates:
- a short **company summary** (bulleted)
- a **personalized cold email pitch** (must start with "Hello," and include 3-5 bullets)

Two modes:
- **Single URL** — quick test for one website
- **Bulk CSV** — upload many websites and download results as CSV
""")

# --- Sidebar: provider & API key ---
st.sidebar.header("API / Provider settings")
provider = st.sidebar.selectbox("Provider", ["OpenAI", "Groq"])
api_key_input = st.sidebar.text_input(f"{provider} API key (or leave blank to use .env)", type="password")
if not api_key_input:
    if provider == "OpenAI":
        API_KEY = os.getenv("OPENAI_API_KEY", "")
    else:
        API_KEY = os.getenv("GROQ_API_KEY", "")
else:
    API_KEY = api_key_input.strip()

model = st.sidebar.selectbox("Model (name)", ["gpt-3.5-turbo"], index=0)
max_tokens = st.sidebar.slider("Max tokens for model response", 300, 2000, 800, step=100)
temperature = st.sidebar.slider("Temperature (creativity)", 0.0, 1.0, 0.2, step=0.05)

# --- Helper functions ---
def fetch_text_from_url(url, timeout=12):
    try:
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=timeout)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for s in soup(["script","style","noscript"]):
            s.decompose()
        texts = []
        for tag in soup.find_all(["h1","h2","h3","p","li"]):
            t = tag.get_text(" ", strip=True)
            if t and len(t) > 20:
                texts.append(t)
        combined = "\n".join(texts)
        if len(combined) > 16000:
            combined = combined[:16000]
        return combined, None
    except Exception as e:
        return "", f"Fetch error: {e}"

def build_system_and_user(url, text):
    system = (
        "You are a concise B2B analyst. From the website text, detect products/services, industry, "
        "target audience (roles), pain points and region. Return ONLY valid JSON with keys: "
        "company_summary (list of short bullets), customers (list), region (string or empty), email_pitch (string). "
        "The email_pitch must start with 'Hello,', include 3-5 bullet points each on its own line starting with '- ', "
        "include one sentence linking the targeted lists to business benefits, and end with 'Let me know if you'd like a sample.'"
    )
    user = f"URL: {url}\n\nWebsite text excerpt:\n{text}\n\nReturn ONLY valid JSON."
    return system, user

def call_chat_api(system_prompt, user_prompt, provider, api_key, model="gpt-3.5-turbo", max_tokens=800, temperature=0.2):
    if not api_key:
        return None, "No API key provided."
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": model,
        "messages": [
            {"role":"system", "content": system_prompt},
            {"role":"user", "content": user_prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    try:
        if provider == "OpenAI":
            endpoint = "https://api.openai.com/v1/chat/completions"
        else:  # Groq uses an OpenAI-compatible endpoint
            endpoint = "https://api.groq.com/openai/v1/chat/completions"
        resp = requests.post(endpoint, headers=headers, json=body, timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        try:
            msg = resp.text
        except Exception:
            msg = str(e)
        return None, f"API error: {e} - response: {msg}"
    # extract model text
    try:
        text = data["choices"][0]["message"]["content"]
    except Exception as e:
        return None, f"Unexpected API response shape: {e} - {json.dumps(data)[:800]}"
    # parse JSON blob
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        js = text[start:end]
        parsed = json.loads(js)
        return parsed, None
    except Exception:
        try:
            parsed = json.loads(text)
            return parsed, None
        except Exception:
            return None, "Failed to parse JSON from model output. Raw output:\n" + text

# --- UI: Mode selection ---
mode = st.radio("Mode", ("Single URL", "Bulk CSV"))
st.markdown("---")

if mode == "Single URL":
    st.subheader("Single URL Analyzer")
    single_url = st.text_input("Enter company website URL", placeholder="https://example.com")
    if st.button("Analyze URL"):
        if not API_KEY:
            st.error("Please provide an API key in the sidebar or set it as an environment variable.")
        elif not single_url:
            st.error("Please enter a URL.")
        else:
            with st.spinner("Fetching website and calling model..."):
                text, err = fetch_text_from_url(single_url)
                if err:
                    st.error(err)
                else:
                    sys_p, user_p = build_system_and_user(single_url, text)
                    parsed, err2 = call_chat_api(sys_p, user_p, provider, API_KEY, model=model, max_tokens=max_tokens, temperature=temperature)
                    if err2:
                        st.error(err2)
                        st.code(parsed or "")
                    else:
                        st.success("Analysis complete ✅")
                        st.markdown("**Company Summary**")
                        for b in parsed.get("company_summary", []):
                            st.write("- " + b)
                        st.markdown("**Detected Customers / Targets**")
                        for c in parsed.get("customers", []):
                            st.write("- " + c)
                        st.markdown("**Region**")
                        st.write(parsed.get("region", ""))
                        st.markdown("**Email Pitch**")
                        st.code(parsed.get("email_pitch", ""))
                        st.download_button("Download JSON result", json.dumps(parsed, indent=2), file_name="outreach_result.json")

elif mode == "Bulk CSV":
    st.subheader("Bulk CSV Processor")
    uploaded = st.file_uploader("Upload CSV with a column named 'url' (or a single column of URLs)", type=["csv"])
    concurrency = st.slider("Pause (secs) between requests (helps avoid rate limits)", 0.5, 5.0, 1.0, step=0.5)
    if uploaded is not None:
        try:
            df = pd.read_csv(uploaded)
        except Exception as e:
            st.error(f"Failed to read CSV: {e}")
            st.stop()
        # detect url column
        if "url" in df.columns:
            urls = df["url"].dropna().astype(str).tolist()
        else:
            # try first column
            urls = df.iloc[:,0].dropna().astype(str).tolist()
        st.info(f"Detected {len(urls)} URLs. Processing...")
        results = []
        progress_bar = st.progress(0)
        for i, u in enumerate(urls):
            progress_bar.progress(int((i/len(urls))*100))
            st.write(f"({i+1}/{len(urls)}) Processing: {u}")
            text, err = fetch_text_from_url(u)
            if err:
                st.write(f" - fetch error: {err}")
                results.append({"url":u, "company_summary":[], "customers":[], "region":"", "email_pitch":"", "error": err})
                time.sleep(concurrency)
                continue
            sys_p, user_p = build_system_and_user(u, text)
            parsed, err2 = call_chat_api(sys_p, user_p, provider, API_KEY, model=model, max_tokens=max_tokens, temperature=temperature)
            if err2:
                st.write(f" - model error: {err2[:200]}")
                results.append({"url":u, "company_summary":[], "customers":[], "region":"", "email_pitch":"", "error": err2})
            else:
                results.append({"url":u, "company_summary": parsed.get("company_summary", []), "customers": parsed.get("customers", []), "region": parsed.get("region",""), "email_pitch": parsed.get("email_pitch",""), "error": ""})
            time.sleep(concurrency)
        progress_bar.progress(100)
        st.success("Bulk processing complete ✅")
        # prepare dataframe for download
        out_rows = []
        for r in results:
            out_rows.append({
                "url": r["url"],
                "company_summary": json.dumps(r["company_summary"], ensure_ascii=False),
                "customers": json.dumps(r["customers"], ensure_ascii=False),
                "region": r["region"],
                "email_pitch": r["email_pitch"],
                "error": r["error"]
            })
        out_df = pd.DataFrame(out_rows)
        csv_bytes = out_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download results CSV", csv_bytes, file_name="outreach_bulk_results.csv", mime="text/csv")
        st.write("Sample output:")
        st.dataframe(out_df.head(20))

st.markdown("---")
st.markdown("Notes: This app calls the selected provider's chat completions endpoint using the API key you provide. "
            "Make sure you respect provider usage policies and rate limits. Keep your API keys secret.")
