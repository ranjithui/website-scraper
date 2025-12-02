import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import re
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# -------------------------
# Basic config
# -------------------------
st.set_page_config(page_title="Website Outreach AI Agent", layout="wide")

GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL_NAME = "llama-3.3-70b-versatile"

# -------------------------
# HTTP Session with retries
# -------------------------
session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retries))
session.mount("http://", HTTPAdapter(max_retries=retries))


# -------------------------
# Scrape Website Content (more robust)
# -------------------------
def scrape_website(url, max_chars=4000):
    try:
        r = session.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # remove scripts/styles and visible noise
        for tag in soup(["script", "style", "noscript", "iframe"]):
            tag.extract()

        text = soup.get_text(separator=" ", strip=True)
        # collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]
    except Exception as e:
        st.warning(f"Failed to scrape {url}: {e}")
        return ""


# -------------------------
# Extract JSON block from model text (robust)
# -------------------------
def extract_json(content):
    if not content:
        return None
    # find first JSON-like block {...}
    match = re.search(r"(\{(?:[^{}]|(?R))*\})", content, flags=re.DOTALL)
    if not match:
        # fallback: try to find lines like key: value pairs and build minimal dict
        return None
    try:
        json_str = match.group(1)
        return json.loads(json_str)
    except Exception:
        # try cleaning trailing commas / single quotes
        cleaned = json_str.replace("\'", "\"")
        cleaned = re.sub(r",\s*}", "}", cleaned)
        cleaned = re.sub(r",\s*\]", "]", cleaned)
        try:
            return json.loads(cleaned)
        except Exception:
            return None


# -------------------------
# Simple industry heuristics to fill ICP bullets and core value
# -------------------------
INDUSTRY_MAP = {
    "mining": {
        "icps": ["Mining operators and site managers", "Fleet and transport managers", "Safety and compliance officers"],
        "value": "compliance, fleet performance, or site support"
    },
    "logistics": {
        "icps": ["Logistics managers", "Transport operations heads", "Warehouse managers"],
        "value": "route optimization, fleet tracking, or cost reduction"
    },
    "saas": {
        "icps": ["VP Product", "Head of Growth", "CTO / Engineering Leads"],
        "value": "product-led growth, onboarding, or developer adoption"
    },
    "healthcare": {
        "icps": ["Hospital administrators", "Clinical leads", "Procurement managers"],
        "value": "clinical workflow efficiency, sourcing, or compliance"
    },
    "finance": {
        "icps": ["Head of Investments", "Portfolio Managers", "COO / Ops"],
        "value": "deal sourcing, compliance, or investor outreach"
    }
}


def detect_industry_and_icps(text, url):
    lower = (text + " " + url).lower()
    for k, v in INDUSTRY_MAP.items():
        if k in lower or k.rstrip("s") in lower:
            return k.capitalize(), v["icps"], v["value"]
    # fallback generic
    return "B2B", ["Procurement / Purchasing Heads", "Operations / Facilities Managers", "IT / Program Leads"], "targeted outreach and lead generation"


# -------------------------
# Build a short deterministic email body locally (no-cost fallback)
# -------------------------
def build_email_local(tone, icps, core_value, company_name, industry):
    # exact format required by the user
    greeting = "Hello" if tone == "Professional" else "Hi"
    greet_line = f"{greeting} [First Name],\n\n"
    bullets = "\n".join([f"• {role}" for role in icps])
    # One benefit sentence
    if tone == "Professional":
        benefit = f"\n\nBased on your focus in **{industry}**, we can reach companies needing **{core_value}**."
        closing = "\n\nInterested in seeing a quick sample?"
    else:
        benefit = f"\n\nI noticed **{company_name}** works in **{industry}** — we can reach buyers needing **{core_value}**."
        closing = "\n\nHappy to share a sample list — want me to send it?"
    return f"{greet_line}We offer targeted email lists to help you connect with:\n{bullets}{benefit}\n\n{closing}"


# -------------------------
# Call Groq model (with retries + concise prompt)
# -------------------------
def groq_ai_generate_summary(url, text):
    """Requests a short JSON summary from the model (company_summary, industry, icps, core_value).
       This is used once per company (bulk-friendly). If the API fails, we fallback to local heuristics.
    """
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""
You are a concise B2B outreach assistant.

Output a JSON object only with fields:
{{
"company_summary": "one 1-2 sentence summary (no more than 30 words)",
"industry": "best-guess single word industry",
"icps": ["role1", "role2", "role3"],
"core_value": "one short phrase describing what contacts need"
}}

Do NOT mention scraping. Company URL: {url}
Website text (short): {text}
Return only JSON.
"""

    body = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.25,
        "max_tokens": 300
    }

    try:
        r = session.post(API_URL, headers=headers, json=body, timeout=30)
        r.raise_for_status()
        res = r.json()
        model_text = res["choices"][0]["message"]["content"]
        parsed = extract_json(model_text)
        if parsed:
            return parsed
        else:
            # Attempt to parse raw text if the model returned plain key:value lines
            try:
                # try simple key:value extraction
                lines = model_text.splitlines()
                data = {}
                for ln in lines:
                    if ":" in ln:
                        k, v = ln.split(":", 1)
                        data[k.strip()] = v.strip()
                if "company_summary" in data or "industry" in data:
                    return {
                        "company_summary": data.get("company_summary", "").strip(),
                        "industry": data.get("industry", "").strip(),
                        "icps": json.loads(data.get("icps")) if "icps" in data else None,
                        "core_value": data.get("core_value", "").strip()
                    }
            except Exception:
                pass
        return None
    except Exception as e:
        # API error — return None so the app falls back to local rules
        st.info(f"Model summary unavailable, using local heuristics. ({e})")
        return None


# -------------------------
# Parse Subject + Email robustly (in case model returns variations)
# -------------------------
def parse_email(content):
    if not content:
        return "", ""
    # try to find "Subject:" line
    subject = ""
    body = content
    lines = content.splitlines()
    for i, ln in enumerate(lines):
        if ln.strip().lower().startswith("subject:"):
            subject = ln.split(":", 1)[1].strip()
            body = "\n".join(lines[i + 1:]).strip()
            break
    return subject, body


# -------------------------
# UI - Single URL Mode
# -------------------------
def analyze_single_url():
    url = st.text_input("Enter Website URL:")
    if st.button("Analyze"):
        if not url:
            st.error("Please provide a URL.")
            return

        with st.spinner("Scraping website..."):
            scraped = scrape_website(url)

        # get model summary (one call) with fallback to local heuristic
        summary = groq_ai_generate_summary(url, scraped)
        if summary:
            company_summary = summary.get("company_summary", "").strip() or "A growing organization"
            industry = summary.get("industry", "").strip() or "B2B"
            icps = summary.get("icps") or []
            core_value = summary.get("core_value", "").strip() or ""
        else:
            industry, icps, core_value = detect_industry_and_icps(scraped, url)
            company_summary = f"A company operating in {industry}"

        # ensure we have 3 ICPs
        if not icps or len(icps) < 3:
            # fill from heuristic map
            detected_industry, icps_default, core_default = detect_industry_and_icps(scraped, url)
            icps = icps_default
            if not core_value:
                core_value = core_default
            if not industry or industry == "B2B":
                industry = detected_industry

        # build both tones locally (deterministic & immediate)
        company_name = re.sub(r"https?://(www\.)?", "", url).split("/")[0]
        professional_body = build_email_local("Professional", icps, core_value, company_name, industry)
        conversational_body = build_email_local("Conversational", icps, core_value, company_name, industry)

        # subjects (short)
        professional_subject = f"Targeted Email Lists for {industry} Outreach"
        conversational_subject = f"Want a sample contact list for {company_name}?"

        st.subheader("📌 Company Insights")
        st.markdown(f"**Summary:** {company_summary}")
        st.markdown(f"**Industry (detected):** {industry}")
        st.markdown("**ICP Roles:**")
        for r in icps:
            st.markdown(f"- {r}")
        st.markdown(f"**Core value:** {core_value}")

        st.subheader("1️⃣ Professional Tone")
        st.text_area("Professional", f"Subject: {professional_subject}\n\n{professional_body}", height=220)

        st.subheader("2️⃣ Conversational Tone")
        st.text_area("Conversational", f"Subject: {conversational_subject}\n\n{conversational_body}", height=220)


# -------------------------
# UI - Bulk CSV Mode
# -------------------------
def analyze_bulk():
    file = st.file_uploader("Upload CSV with 'url' column", type=["csv"])
    if file is not None:
        df = pd.read_csv(file)
        if "url" not in df.columns:
            st.error("CSV must contain a column named 'url'")
            return

        if st.button("Run Bulk"):
            results = []
            progress = st.progress(0)
            total = len(df)
            for idx, row in df.iterrows():
                url = row["url"]
                scraped = scrape_website(url)
                summary = groq_ai_generate_summary(url, scraped)
                if summary:
                    company_summary = summary.get("company_summary", "").strip() or "A growing organization"
                    industry = summary.get("industry", "").strip() or "B2B"
                    icps = summary.get("icps") or []
                    core_value = summary.get("core_value", "").strip() or ""
                else:
                    industry, icps, core_value = detect_industry_and_icps(scraped, url)
                    company_summary = f"A company operating in {industry}"

                if not icps or len(icps) < 3:
                    _, icps_default, core_default = detect_industry_and_icps(scraped, url)
                    icps = icps_default
                    if not core_value:
                        core_value = core_default

                company_name = re.sub(r"https?://(www\.)?", "", url).split("/")[0]
                prof_body = build_email_local("Professional", icps, core_value, company_name, industry)
                conv_body = build_email_local("Conversational", icps, core_value, company_name, industry)
                prof_subject = f"Targeted Email Lists for {industry} Outreach"
                conv_subject = f"Want a sample contact list for {company_name}?"

                results.append({
                    "url": url,
                    "company_summary": company_summary,
                    "industry": industry,
                    "icp_1": icps[0] if len(icps) > 0 else "",
                    "icp_2": icps[1] if len(icps) > 1 else "",
                    "icp_3": icps[2] if len(icps) > 2 else "",
                    "professional_subject": prof_subject,
                    "professional_body": prof_body,
                    "conversational_subject": conv_subject,
                    "conversational_body": conv_body
                })

                progress.progress((idx + 1) / total)

            result_df = pd.DataFrame(results)
            st.success("Bulk generation completed.")
            st.dataframe(result_df)
            st.download_button(
                "Download Results CSV",
                result_df.to_csv(index=False).encode("utf-8"),
                "email_results.csv",
                "text/csv"
            )


# -------------------------
# App Layout
# -------------------------
st.title("🌐 Website Outreach AI Agent — Short 2-Tone Emails")

mode = st.radio("Select Mode", ["Single URL", "Bulk CSV Upload"])
if mode == "Single URL":
    analyze_single_url()
else:
    analyze_bulk()
