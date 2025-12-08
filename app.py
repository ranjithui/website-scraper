# streamlit_research_selenium.py
import streamlit as st
import pandas as pd
import time
import os
import json
import re
import traceback
from datetime import datetime
from bs4 import BeautifulSoup

# selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

import requests

# -------------------------
# Config
# -------------------------
DELAY_SECONDS = 30
LOCAL_RESULTS_FILE = "research_results.csv"
API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL_NAME = "llama-3.3-70b-versatile"
MAX_RENDER_WAIT = 8  # seconds to wait after load to give JS time

st.set_page_config(page_title="Research Collector (Selenium)", layout="wide")
st.title("🔎 Research Collector — Headless Selenium + Debug logs (30s delay)")

# -------------------------
# Helpers
# -------------------------
def log_console(msg):
    print(f"[{datetime.now().isoformat()}] {msg}", flush=True)

def ensure_driver(headless=True):
    """Start a Chrome webdriver (reused across pages)."""
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--disable-blink-features=AutomationControlled")
    # optional user-agent to reduce bot detection
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115 Safari/537.36")
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        log_console("Failed to start webdriver: " + str(e))
        log_console(traceback.format_exc())
        return None

def fetch_page_with_selenium(driver, url):
    """Return page_source and some debug info."""
    debug = {"url": url, "status": "ok", "html_len": 0, "error": "", "final_url": url}
    try:
        if not url:
            raise ValueError("Empty URL")
        if not url.startswith("http"):
            url = "https://" + url
        driver.get(url)
        # give JS some time to execute
        time.sleep(min(MAX_RENDER_WAIT, 2))
        # optionally additional small wait for dynamic content
        # try a short wait loop to see if body exists / length increases
        prev_len = 0
        for _ in range(3):
            html = driver.page_source or ""
            if len(html) > prev_len:
                prev_len = len(html)
            time.sleep(0.6)
        html = driver.page_source or ""
        debug["html_len"] = len(html)
        debug["final_url"] = driver.current_url
        # Try extracting http status via performance logs isn't always available; skip
        return html, debug
    except TimeoutException as te:
        debug["status"] = "timeout"
        debug["error"] = str(te)
        log_console("Timeout fetching: " + url)
        return "", debug
    except WebDriverException as we:
        debug["status"] = "webdriver_error"
        debug["error"] = str(we)
        log_console("WebDriverException for: " + url + " -> " + str(we))
        return "", debug
    except Exception as e:
        debug["status"] = "error"
        debug["error"] = str(e)
        log_console("Error fetching page: " + str(e))
        log_console(traceback.format_exc())
        return "", debug

def extract_contact_emails(text):
    emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    return ", ".join(sorted(set(emails)))

def extract_meta(soup):
    meta = {}
    title = soup.find("title")
    meta['title'] = title.get_text(strip=True) if title else ""
    desc = ""
    m = soup.find("meta", attrs={"name":"description"})
    if m and m.get("content"):
        desc = m.get("content")
    else:
        m2 = soup.find("meta", attrs={"property":"og:description"})
        desc = m2.get("content") if (m2 and m2.get("content")) else desc
    meta['meta_description'] = desc
    return meta

def call_ai_insights(groq_api_key, url, scraped_text):
    keys = [
        "website_url", "company_name", "about", "services", "ideal_customers",
        "unique_value", "contact_info", "competitors", "tech_stack",
        "pricing_model", "target_geography", "call_to_action", "testimonials",
        "employee_size"
    ]
    prompt = f"""
You are a concise business analyst. Extract ONLY JSON with the following keys exactly:
{json.dumps(keys, indent=2)}

For each key provide a short string or CSV-like string (or empty string if unknown).
Use the website content below. Be conservative and short. For 'employee_size' give an estimate like "1-10", "11-50", "51-200", "201-1000", or "1000+".

Company URL: {url}

Website Content:
{scraped_text}
"""
    if not groq_api_key:
        # return minimal structure if no key provided
        return {k: (url if k == "website_url" else "") for k in keys}
    try:
        headers = {"Authorization": f"Bearer {groq_api_key}", "Content-Type": "application/json"}
        body = {"model": MODEL_NAME, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2}
        r = requests.post(API_URL, headers=headers, json=body, timeout=60)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        # extract first JSON-looking object
        start = content.find("{")
        end = content.rfind("}") + 1
        if start == -1 or end == -1:
            # fallback: return partial
            return {k: "" if k!="website_url" else url for k in keys}
        parsed = json.loads(content[start:end])
        # normalize into strings
        out = {}
        for k in keys:
            val = parsed.get(k, "")
            if isinstance(val, list):
                out[k] = ", ".join([str(x).strip() for x in val if x])
            elif isinstance(val, dict):
                out[k] = json.dumps(val, ensure_ascii=False)
            elif val is None:
                out[k] = ""
            else:
                out[k] = str(val).strip()
        out["website_url"] = url
        return out
    except Exception as e:
        log_console("AI call error: " + str(e))
        log_console(traceback.format_exc())
        return {k: (url if k == "website_url" else "") for k in keys}

def load_local_results():
    if os.path.exists(LOCAL_RESULTS_FILE):
        try:
            return pd.read_csv(LOCAL_RESULTS_FILE)
        except Exception as e:
            log_console("Failed to read local results: " + str(e))
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
# UI
# -------------------------
st.sidebar.header("Inputs & Settings")
uploaded = st.sidebar.file_uploader("Upload CSV or Excel with 'Website' column", type=["csv", "xlsx", "xls"])
use_sample = st.sidebar.checkbox("Use sample websites (demo)", value=False)
groq_key = st.sidebar.text_input("GROQ API Key (optional)", type="password")
headless_opt = st.sidebar.checkbox("Run headless Chrome (recommended)", value=True)
max_retries = st.sidebar.number_input("Retries per URL", min_value=0, max_value=5, value=2)
delay_seconds = st.sidebar.number_input("Delay between rows (seconds)", min_value=5, max_value=600, value=DELAY_SECONDS)

if use_sample and uploaded is None:
    input_df = pd.DataFrame({"Website": ["https://example.com", "https://openai.com", "https://python.org"]})
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
    st.info("Upload a CSV/Excel with 'Website' column or enable sample.")
    st.stop()

# normalize website column
possible_cols = [c for c in input_df.columns if c.strip().lower() in ("website", "url", "website_url")]
if not possible_cols:
    st.error("Uploaded file must contain a 'Website' or 'URL' column.")
    st.stop()

input_df = input_df.rename(columns={possible_cols[0]: "Website"})
st.write(f"Loaded {len(input_df)} rows.")
st.dataframe(input_df.head(8))

# session state init
if "input_df" not in st.session_state or st.session_state.input_df.shape[0] != input_df.shape[0]:
    st.session_state.input_df = input_df.copy()
    st.session_state.current_index = 0
    # load existing results for resume
    existing = load_local_results()
    if not existing.empty:
        processed = set(existing['website_url'].astype(str).str.lower().str.strip().tolist())
        idx = 0
        for w in st.session_state.input_df["Website"].astype(str).tolist():
            if str(w).strip().lower() in processed:
                idx += 1
            else:
                break
        st.session_state.current_index = idx
        st.session_state.results_df = existing
    else:
        cols = [
            "website_url", "company_name", "about", "services", "ideal_customers",
            "unique_value", "contact_info", "competitors", "tech_stack",
            "pricing_model", "target_geography", "call_to_action", "testimonials",
            "employee_size", "debug_html_len", "debug_final_url", "status", "error", "processed_at"
        ]
        st.session_state.results_df = pd.DataFrame(columns=cols)
    st.session_state.running = False
    st.session_state.driver = None

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
    if st.button("Stop & Close driver"):
        st.session_state.running = False
        try:
            if st.session_state.driver:
                st.session_state.driver.quit()
                st.session_state.driver = None
        except Exception:
            pass
        st.success("Stopped and closed driver.")

with col3:
    if st.button("Reset progress (keep upload)"):
        st.session_state.results_df = pd.DataFrame(columns=st.session_state.results_df.columns)
        if os.path.exists(LOCAL_RESULTS_FILE):
            try:
                os.remove(LOCAL_RESULTS_FILE)
            except Exception:
                pass
        st.session_state.current_index = 0
        st.session_state.running = False
        st.warning("Progress reset.")

st.sidebar.write(f"Resume index: {st.session_state.current_index} / {len(st.session_state.input_df)}")
st.sidebar.write(f"Saved rows: {len(st.session_state.results_df)}")

progress_placeholder = st.empty()
logs_pl_
