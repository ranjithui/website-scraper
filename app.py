# app.py
import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import json
import time
import os
import traceback
from urllib3.util import Retry
from requests.adapters import HTTPAdapter

# ---------------------------
# Page config
# ---------------------------
st.set_page_config(page_title="Bulk Website → AI Insights (Improved)", layout="wide")

# ---------------------------
# CONFIG (Uses Streamlit Secrets)
# ---------------------------
GROQ_KEY = st.secrets.get("GROQ_API_KEY", None)
API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"

# Check API key
if not GROQ_KEY:
    st.error("GROQ_API_KEY not found in Streamlit secrets. Add it before running.")
    st.stop()

# ---------------------------
# Utilities: HTTP Session with retries
# ---------------------------
def make_session(retries=3, backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504)):
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=frozenset(['GET', 'POST'])
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    # set a polite user agent
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; PhoenixxBot/1.0; +https://yourdomain.example)",
        "Accept-Language": "en-US,en;q=0.9"
    })
    return session

SESSION = make_session()

# ---------------------------
# URL fallback attempts
# ---------------------------
FALLBACK_PATTERNS = [
    "https://{domain}",
    "http://{domain}",
    "https://www.{domain}",
    "http://www.{domain}"
]

COMMON_PATHS = [
    "/", "/about", "/about-us", "/aboutus", "/company", "/services", "/service",
    "/products", "/product", "/solutions", "/solution", "/what-we-do", "/team",
    "/contact", "/contact-us", "/careers"
]

# ---------------------------
# Scrape function (focus on relevant pages)
# ---------------------------
def try_urls(domain, session=SESSION, timeout=10):
    """Try fallback patterns and return the first successful base_url (200) or raise."""
    last_err = None
    for pattern in FALLBACK_PATTERNS:
        url = pattern.format(domain=domain.strip().strip("/"))
        try:
            r = session.get(url, timeout=timeout)
            if r.status_code == 200:
                return url
            last_err = f"{url} returned {r.status_code}"
        except Exception as e:
            last_err = str(e)
    raise Exception(f"All fallback URIs failed for {domain}: {last_err}")

def scrape_relevant(domain, session=SESSION, timeout=10, char_limit=4000):
    """
    Visit a small set of likely pages and collect text.
    Returns concatenated text (trimmed).
    """
    try:
        base = try_urls(domain, session=session, timeout=timeout)
    except Exception as e:
        return f"SCRAPE_ERROR_BASEURL: {str(e)}"

    collected = []
    for path in COMMON_PATHS:
        full = base.rstrip("/") + (path if path.startswith("/") else "/" + path)
        try:
            r = session.get(full, timeout=timeout)
            if r.status_code == 200 and r.text:
                soup = BeautifulSoup(r.text, "html.parser")
                # remove scripts/styles
                for script in soup(["script", "style", "noscript"]):
                    script.extract()
                text = soup.get_text(" ", strip=True)
                if text:
                    collected.append(text)
        except Exception:
            # skip path errors silently, keep going
            continue

        # small optimization: stop when we have enough content
        if sum(len(s) for s in collected) >= char_limit:
            break

    # fallback: if nothing was collected from paths, try base homepage again gracefully
    if not collected:
        try:
            r = session.get(base, timeout=timeout)
            soup = BeautifulSoup(r.text, "html.parser")
            for script in soup(["script", "style", "noscript"]):
                script.extract()
            text = soup.get_text(" ", strip=True)
            if text:
                collected.append(text)
        except Exception as e:
            return f"SCRAPE_ERROR_FINAL: {str(e)}"

    combined = " ".join(collected)
    return combined[:char_limit]

# ---------------------------
# AI prompt function (strict JSON output, B2B only except HNWI/UHNWI)
# ---------------------------
def get_ai_insights(domain, scraped_text):
    prompt = f"""
You are an extractor that returns ONLY a CLEAN, VALID JSON (no extra text, no explanation).
Extract structured company insights from the website content.

Important rules:
- Return only JSON, and ensure it is valid JSON.
- Include only B2B target audiences. EXCLUDE B2C audiences UNLESS they are High Net Worth Individuals (HNWI) or Ultra High Net Worth Individuals (UHNWI) — include these only if explicitly referenced on the website.
- If any field is not available, return an empty string or empty array as appropriate.
- Keep "company_summary" brief (1-2 sentences).
- Use short, comma-light strings for arrays.

Return JSON with this exact format:

{
  "company_name": "",
  "company_summary": "",
  "main_products": [],
  "ideal_customers": [],
  "ideal_audience": [],
  "industry": "",
  "countries_of_operation": []
}

Website domain: {domain}
Scraped content (trimmed): {scraped_text}
"""

    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }

    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 800
    }

    try:
        r = SESSION.post(API_URL, json=body, headers=headers, timeout=60)
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"]

        # Try to strictly extract first JSON object in the response
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == -1:
            return {"error": "Invalid AI Response", "raw": raw}

        payload = raw[start:end]
        return json.loads(payload)

    except Exception as e:
        # include some debug info for UI
        return {"error": str(e), "trace": traceback.format_exc()}

# ---------------------------
# Checkpoint helpers
# ---------------------------
CHECKPOINT_PATH = "/tmp/ai_insights_checkpoint.csv"

def save_checkpoint(df):
    # ensure temp dir exists
    try:
        df.to_csv(CHECKPOINT_PATH, index=False)
    except Exception as e:
        st.warning(f"Failed to write checkpoint: {e}")

def load_checkpoint():
    if os.path.exists(CHECKPOINT_PATH):
        try:
            return pd.read_csv(CHECKPOINT_PATH)
        except Exception:
            return None
    return None

# ---------------------------
# Batch Processor (with checkpointing)
# ---------------------------
def process_csv(df, website_column, live_box, delay_sec=20, row_limit=None):
    """
    Processes rows and writes checkpoint after every row.
    Returns final dataframe (may be partial if interrupted).
    """
    results = []
    start_index = 0

    # if checkpoint exists, try to resume automatically: use same input order assumption
    checkpoint_df = load_checkpoint()
    if checkpoint_df is not None and len(checkpoint_df) > 0:
        # if checkpoint has a column named the same as website values, determine resume index
        # naive resume: skip rows whose website already present in checkpoint
        processed_websites = set(checkpoint_df[website_column].astype(str).tolist()) if website_column in checkpoint_df.columns else set()
    else:
        processed_websites = set()

    try:
        total = len(df)
        for i, row in df.iterrows():
            if row_limit and i >= row_limit:
                break

            website = str(row[website_column]).strip()
            if not website or website.lower() in ["nan", "none"]:
                live_box.warning(f"Skipping empty website at row {i}")
                continue

            # skip if already processed in checkpoint
            if website in processed_websites:
                live_box.info(f"Skipping {i+1}/{total} `{website}` — already in checkpoint")
                # try to include previous processed row into results to aggregate final_df
                if checkpoint_df is not None:
                    prev_rows = checkpoint_df[checkpoint_df[website_column].astype(str) == website]
                    if not prev_rows.empty:
                        results.append(prev_rows.iloc[0].to_dict())
                continue

            live_box.markdown(f"### 🔍 Processing {i+1}/{total} — `{website}`")
            try:
                scraped = scrape_relevant(website)
                ai_data = get_ai_insights(website, scraped)

                live_box.write("📌 **Insights (AI):**")
                # if it's error, show it
                if isinstance(ai_data, dict) and ("error" in ai_data):
                    live_box.json(ai_data)
                else:
                    live_box.json(ai_data)

                combined = {**row.to_dict(), **(ai_data if isinstance(ai_data, dict) else {})}
                results.append(combined)

                # update checkpoint
                checkpoint_df_new = pd.DataFrame(results)
                # if there was a previous checkpoint, merge to avoid losing previous rows
                if os.path.exists(CHECKPOINT_PATH):
                    try:
                        old = pd.read_csv(CHECKPOINT_PATH)
                        # concat unique by website
                        merged = pd.concat([old, checkpoint_df_new], ignore_index=True)
                        merged = merged.drop_duplicates(subset=[website_column], keep="first")
                        save_checkpoint(merged)
                    except Exception:
                        save_checkpoint(checkpoint_df_new)
                else:
                    save_checkpoint(checkpoint_df_new)

                # polite delay
                time.sleep(delay_sec)

            except Exception as e:
                live_box.error(f"Error processing `{website}`: {e}")
                # still write checkpoint with what we have so far
                save_checkpoint(pd.DataFrame(results))
                continue

        # final DataFrame: try to load checkpoint to ensure all rows present
        final_df = load_checkpoint()
        if final_df is None:
            final_df = pd.DataFrame(results)
        return final_df

    except Exception as e:
        # on any unexpected termination, save what we have
        save_checkpoint(pd.DataFrame(results))
        raise e

# ---------------------------
# UI
# ---------------------------
st.title("🌍 Bulk Website → AI Insights Generator (Improved)")

st.markdown("""
**Features added**
- Fallback URIs (https/http/www)
- Limited-page scraping to avoid full-site noise
- B2B-only audience extraction (HNWI/UHNWI allowed only if present)
- Checkpointing after every row (auto-save to `/tmp/ai_insights_checkpoint.csv`)
- Resume and download partial results
""")

uploaded = st.file_uploader("📤 Upload CSV (must contain website column)", type=["csv"])

# options
st.sidebar.header("Processing Options")
delay_sec = st.sidebar.number_input("Delay between requests (seconds)", min_value=1, max_value=120, value=20)
row_limit = st.sidebar.number_input("Row limit (0 = all)", min_value=0, value=0)
resume_from_checkpoint = st.sidebar.checkbox("Resume from existing checkpoint (if found)", value=True)
website_col_hint = st.sidebar.text_input("Website column name (leave empty to auto-detect)", value="")

st.sidebar.markdown("---")
if os.path.exists(CHECKPOINT_PATH):
    st.sidebar.success(f"Checkpoint found: {CHECKPOINT_PATH} ({os.path.getsize(CHECKPOINT_PATH)} bytes)")
    if st.sidebar.button("Download latest checkpoint"):
        try:
            with open(CHECKPOINT_PATH, "rb") as f:
                st.download_button("📥 Download checkpoint CSV", data=f, file_name="ai_insights_checkpoint.csv", mime="text/csv")
        except Exception as e:
            st.sidebar.error(f"Failed to serve checkpoint: {e}")

# show previous checkpoint summary
checkpoint_df = load_checkpoint()
if checkpoint_df is not None:
    st.sidebar.markdown(f"**Checkpoint preview** ({len(checkpoint_df)} rows):")
    st.sidebar.dataframe(checkpoint_df.head(5))

if uploaded:
    df = pd.read_csv(uploaded)
    st.write("📁 Uploaded file preview:")
    st.dataframe(df.head())

    # auto-detect website column if not provided
    if website_col_hint and website_col_hint in df.columns:
        website_column = website_col_hint
    else:
        auto_col = None
        for c in df.columns:
            if c.lower() in ["website", "url", "domain", "site"]:
                auto_col = c
                break
        website_column = st.selectbox("Select website column:", df.columns.tolist(),
                                      index=df.columns.tolist().index(auto_col) if auto_col else 0)

    # test run controls
    st.write("Controls:")
    start_button = st.button("🚀 Start Processing")
    stop_button = st.button("⛔ Stop (this will attempt to gracefully stop)")

    # small testing controls
    if row_limit == 0:
        row_limit = None

    live_box = st.empty()

    if start_button:
        # if resume is true and checkpoint exists, try to merge/resume
        if resume_from_checkpoint and checkpoint_df is not None:
            # we will attempt to not re-run websites present in checkpoint
            live_box.info("Resuming from checkpoint; items already processed will be skipped.")
        try:
            final_df = process_csv(df, website_column, live_box, delay_sec=delay_sec, row_limit=row_limit)
            st.success("🎉 Processing complete!")
            st.dataframe(final_df.head(50))

            # write final CSV and offer download
            out_path = "/tmp/ai_website_insights_final.csv"
            final_df.to_csv(out_path, index=False)
            with open(out_path, "rb") as f:
                st.download_button("📥 Download Final CSV", data=f, file_name="ai_website_insights.csv", mime="text/csv")

            # also keep checkpoint saved
            save_checkpoint(final_df)

        except Exception as e:
            live_box.error(f"Processing terminated with error: {e}")
            st.error("Processing stopped — partial results saved to checkpoint (if any). You can download the checkpoint from the sidebar.")
            st.exception(traceback.format_exc())

    # quick option to just download (or view) checkpoint without starting
    if st.button("🔁 Show current checkpoint (if any)"):
        ck = load_checkpoint()
        if ck is not None:
            st.write(f"Checkpoint rows: {len(ck)}")
            st.dataframe(ck.head(50))
            with open(CHECKPOINT_PATH, "rb") as f:
                st.download_button("📥 Download checkpoint CSV", data=f, file_name="ai_insights_checkpoint.csv", mime="text/csv")
        else:
            st.info("No checkpoint found.")

else:
    st.info("Upload a CSV to begin. The CSV must contain a column with website domains or URLs.")
