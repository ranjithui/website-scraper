import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import json
import re
import time
import traceback
import os
from datetime import datetime

# -------------------------
# Config
# -------------------------
DELAY_SECONDS = 30  # 30-second delay between rows
LOCAL_RESULTS_FILE = "research_results.csv"
API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL_NAME = "llama-3.3-70b-versatile"

st.set_page_config(page_title="Local Research Collector", layout="wide")
st.title("🔎 Local Research Collector (no pitches)")

# -------------------------
# Helpers
# -------------------------
def log_console(msg):
    print(f"[{datetime.now().isoformat()}] {msg}", flush=True)

def safe_get_text_from_url(url, max_chars=8000, timeout=12):
    try:
        if not url:
            return ""
        if not url.startswith("http"):
            url = "https://" + url
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        return text[:max_chars]
    except Exception as e:
        log_console("Scrape error: " + str(e))
        log_console(traceback.format_exc())
        return ""

def extract_json(content):
    """Try to pull JSON object out of model response."""
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start == -1 or end == -1:
            return {}
        data = json.loads(content[start:end])
        return data if isinstance(data, dict) else {}
    except Exception as e:
        log_console("JSON extract error: " + str(e))
        log_console(traceback.format_exc())
        return {}

def call_ai_for_insights(groq_api_key, url, scraped_text):
    """
    Calls your Groq model to extract the requested insight fields as JSON.
    Returns a dict with keys (strings) for each requested field (values may be empty).
    """
    # requested fields according to user's selection:
    keys = [
        "website_url", "company_name", "about", "services", "ideal_customers",
        "unique_value", "contact_info", "competitors", "tech_stack",
        "pricing_model", "target_geography", "call_to_action", "testimonials",
        "employee_size"
    ]

    # Build prompt asking for ONLY JSON in exact format
    prompt = f"""
You are a concise business analyst. Extract ONLY JSON with the following keys exactly:
{json.dumps(keys, indent=2)}

For each key provide a string or array as appropriate. If you cannot find data, return an empty string or empty array.
Be conservative and short. For 'services' return a comma-separated string or an array. For 'ideal_customers' return short bullet-like items or array.
Use the website content below to infer values. For 'employee_size' give an estimate like "1-10", "11-50", "51-200", "201-1000", or "1000+" if possible.

Company URL: {url}

Website Content:
{scraped_text}
"""
    if not groq_api_key:
        # If no API key provided, return minimal structure with website_url filled
        return {k: (url if k == "website_url" else "") for k in keys}

    try:
        headers = {"Authorization": f"Bearer {groq_api_key}", "Content-Type": "application/json"}
        body = {"model": MODEL_NAME, "messages": [{"role": "user", "content": prompt}], "temperature": 0.25}
        r = requests.post(API_URL, headers=headers, json=body, timeout=60)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        parsed = extract_json(content)

        # Ensure all keys exist
        data = {}
        for k in keys:
            if k in parsed:
                data[k] = parsed[k]
            else:
                # try some tolerant mappings if the model used slightly different keys
                lowered = {kk.lower(): parsed[kk] for kk in parsed}
                if k.lower() in lowered:
                    data[k] = lowered[k.lower()]
                else:
                    data[k] = "" if not isinstance(parsed, list) else []
        # Always set website_url field explicitly
        data["website_url"] = url
        # Normalize arrays to comma-joined strings for CSV outputs
        for k in ["services", "ideal_customers", "competitors", "tech_stack", "testimonials"]:
            if isinstance(data.get(k), list):
                data[k] = ", ".join([str(x).strip() for x in data[k] if x])
        # Ensure simple string types
        for k in keys:
            if isinstance(data.get(k), dict):
                data[k] = json.dumps(data[k], ensure_ascii=False)
            if data.get(k) is None:
                data[k] = ""
        return data
    except Exception as e:
        log_console("AI insights error: " + str(e))
        log_console(traceback.format_exc())
        # return minimal structure on failure
        return {k: (url if k == "website_url" else "") for k in keys}

def load_local_results():
    if os.path.exists(LOCAL_RESULTS_FILE):
        try:
            df = pd.read_csv(LOCAL_RESULTS_FILE)
            return df
        except Exception as e:
            log_console("Failed to read existing local results: " + str(e))
            log_console(traceback.format_exc())
            return pd.DataFrame()
    return pd.DataFrame()

def save_local_results(df):
    try:
        df.to_csv(LOCAL_RESULTS_FILE, index=False, encoding="utf-8")
    except Exception as e:
        log_console("Failed writing local results: " + str(e))
        log_console(traceback.format_exc())

# -------------------------
# UI: Upload & Controls
# -------------------------
st.sidebar.header("Inputs")
uploaded = st.sidebar.file_uploader("Upload CSV or Excel with 'Website' column", type=["csv", "xlsx", "xls"])
use_sample = st.sidebar.checkbox("Use sample websites (demo)", value=False)

if use_sample and uploaded is None:
    sample = pd.DataFrame({
        "Website": ["example.com", "openai.com", "python.org"],
    })
    input_df = sample
else:
    input_df = None
    if uploaded:
        try:
            name = uploaded.name.lower()
            if name.endswith(".csv"):
                input_df = pd.read_csv(uploaded, encoding="utf-8")
            else:
                input_df = pd.read_excel(uploaded, engine="openpyxl")
        except Exception:
            uploaded.seek(0)
            input_df = pd.read_csv(uploaded, encoding="latin1", errors="ignore")

if input_df is None:
    st.info("Upload a CSV/Excel with a 'Website' column (or toggle sample).")
else:
    # normalize Website column name possibilities
    possible_cols = [c for c in input_df.columns if c.strip().lower() in ("website", "url", "website_url")]
    if not possible_cols:
        st.error("Uploaded file must contain a 'Website' or 'URL' column.")
    else:
        website_col = possible_cols[0]
        input_df = input_df.rename(columns={website_col: "Website"})
        st.write(f"Loaded {len(input_df)} rows from input.")
        st.dataframe(input_df.head(10))

        # session state init
        if "input_df" not in st.session_state or st.session_state.input_df.shape[0] != input_df.shape[0]:
            st.session_state.input_df = input_df.copy()
            st.session_state.start_index = 0
            # load existing results and determine resume index by Website match
            existing = load_local_results()
            if not existing.empty:
                processed_urls = set(existing['website_url'].astype(str).str.lower().str.strip().tolist())
                idx = 0
                for w in st.session_state.input_df["Website"].astype(str).tolist():
                    if str(w).strip().lower() in processed_urls:
                        idx += 1
                    else:
                        break
                st.session_state.start_index = idx
                st.session_state.results_df = existing
            else:
                # create empty results_df with chosen columns
                columns = [
                    "website_url", "company_name", "about", "services", "ideal_customers",
                    "unique_value", "contact_info", "competitors", "tech_stack",
                    "pricing_model", "target_geography", "call_to_action", "testimonials",
                    "employee_size"
                ]
                st.session_state.results_df = pd.DataFrame(columns=columns)

            st.session_state.current_index = st.session_state.start_index
            st.session_state.running = False
            st.session_state.last_processed = None

        # API key input (optional)
        groq_key = st.sidebar.text_input("GROQ API Key (optional — leave blank to disable AI calls)", type="password")

        # Controls
        col1, col2, col3 = st.columns([1,1,2])
        with col1:
            if st.session_state.running:
                if st.button("Pause"):
                    st.session_state.running = False
            else:
                if st.button("Start Processing"):
                    st.session_state.running = True

        with col2:
            if st.button("Reset progress (keep uploaded file)"):
                st.session_state.results_df = pd.DataFrame(columns=st.session_state.results_df.columns)
                if os.path.exists(LOCAL_RESULTS_FILE):
                    try:
                        os.remove(LOCAL_RESULTS_FILE)
                    except Exception:
                        log_console("Couldn't remove local results file")
                st.session_state.current_index = 0
                st.session_state.running = False
                st.warning("Progress reset. Start again when ready.")

        with col3:
            st.write(f"Next index: {st.session_state.current_index} / {len(st.session_state.input_df)}")
            st.write(f"Saved rows: {len(st.session_state.results_df)}")

        # placeholders
        progress_placeholder = st.empty()
        status_placeholder = st.empty()
        sample_preview = st.empty()

        # Processing loop
        while st.session_state.running and st.session_state.current_index < len(st.session_state.input_df):
            i = st.session_state.current_index
            row = st.session_state.input_df.iloc[i].to_dict()
            website = str(row.get("Website","")).strip()

            status_placeholder.info(f"Processing row {i+1}/{len(st.session_state.input_df)} → {website}")
            log_console(f"Processing index {i} -> {website}")

            try:
                scraped = safe_get_text_from_url(website)
                insights = call_ai_for_insights(groq_key, website, scraped)

                # ensure all columns exist in proper order
                record = {
                    "website_url": insights.get("website_url", website),
                    "company_name": insights.get("company_name", ""),
                    "about": insights.get("about", ""),
                    "services": insights.get("services", ""),
                    "ideal_customers": insights.get("ideal_customers", ""),
                    "unique_value": insights.get("unique_value", ""),
                    "contact_info": insights.get("contact_info", ""),
                    "competitors": insights.get("competitors", ""),
                    "tech_stack": insights.get("tech_stack", ""),
                    "pricing_model": insights.get("pricing_model", ""),
                    "target_geography": insights.get("target_geography", ""),
                    "call_to_action": insights.get("call_to_action", ""),
                    "testimonials": insights.get("testimonials", ""),
                    "employee_size": insights.get("employee_size", "")
                }

                # append to results_df
                st.session_state.results_df = pd.concat([st.session_state.results_df, pd.DataFrame([record])], ignore_index=True)

                # save locally after every row
                save_local_results(st.session_state.results_df)

                # preview
                sample_preview.markdown("### Latest Insight (preview)")
                sample_preview.write(pd.DataFrame([record]).T.rename(columns={0:"value"}))

                # advance
                st.session_state.current_index += 1
                st.session_state.last_processed = website

            except Exception as e:
                log_console("Processing error: " + str(e))
                log_console(traceback.format_exc())
                # record error row (website + error note)
                err_rec = {"website_url": website}
                for c in st.session_state.results_df.columns:
                    if c not in err_rec:
                        err_rec[c] = ""
                err_rec["company_name"] = ""
                err_rec["about"] = ""
                err_rec["unique_value"] = ""
                err_rec["contact_info"] = ""
                err_rec["testimonials"] = ""
                err_rec["employee_size"] = ""
                # Optionally record error in a separate column — but per request we keep fields minimal
                st.session_state.results_df = pd.concat([st.session_state.results_df, pd.DataFrame([err_rec])], ignore_index=True)
                save_local_results(st.session_state.results_df)
                st.session_state.current_index += 1

            # update progress bar
            processed = st.session_state.current_index
            total = len(st.session_state.input_df)
            frac = processed / total if total else 0
            progress_placeholder.progress(min(frac, 1.0))
            status_placeholder.write(f"Sleeping for {DELAY_SECONDS} seconds before next row...")
            # sleep loop allowing user to pause
            sleep_left = DELAY_SECONDS
            while sleep_left > 0 and st.session_state.running:
                time.sleep(1)
                sleep_left -= 1
            if not st.session_state.running:
                status_placeholder.warning("Processing paused by user.")
                break

        # finished
        if st.session_state.current_index >= len(st.session_state.input_df):
            st.success("🎉 All rows processed!")
            st.session_state.running = False

        # show results & download
        st.subheader("Research Results Snapshot")
        st.dataframe(st.session_state.results_df)

        csv = st.session_state.results_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download research_results.csv", csv, "research_results.csv", "text/csv")

        st.info("Notes: Runs locally. Keep machine awake while processing. If you restart the app it will resume from research_results.csv (match by website).")
