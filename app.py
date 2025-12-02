import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import time

st.set_page_config(page_title="Website Outreach AI Agent", layout="wide")

# -------------------------
# Config / API
# -------------------------
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL_NAME = "llama-3.3-70b-versatile"

# Static signature (choice A)
STATIC_SIGNATURE = "Best regards,\nRanjith G"

# -------------------------
# Utilities
# -------------------------
def safe_post(payload):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    try:
        r = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

# -------------------------
# Scrape Website Content
# -------------------------
def scrape_website(url):
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for s in soup(["script", "style", "noscript"]):
            s.extract()
        text = soup.get_text(separator=" ", strip=True)
        return text[:4000]
    except Exception as e:
        st.warning(f"Failed to scrape {url}: {e}")
        return ""

# -------------------------
# JSON Insight Generation (first step)
# -------------------------
def generate_insights(url, scraped_text):
    prompt = f"""
You are an assistant that extracts short structured company insights clearly and concisely.

Return JSON only in this exact format:

{{
  "company_summary": "two short sentences describing company",
  "ideal_customers": ["ICP role 1", "ICP role 2", "ICP role 3", "ICP role 4", "ICP role 5"],
  "solutions": ["solution 1", "solution 2"],
  "industry": "short industry label (e.g., Mining, Financial Services, Logistics)"
}}

URL: {url}
Scraped Content: {scraped_text}
"""
    body = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0
    }
    res = safe_post(body)
    if res is None or "error" in res:
        return None
    try:
        text = res["choices"][0]["message"]["content"]
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == -1:
            return None
        j = json.loads(text[start:end])
        # Normalize
        j.setdefault("company_summary", "")
        j.setdefault("ideal_customers", [])
        j.setdefault("solutions", [])
        j.setdefault("industry", "")
        if not isinstance(j["ideal_customers"], list):
            j["ideal_customers"] = []
        return j
    except Exception:
        return None

# -------------------------
# Tone rules (strong differentiation)
# -------------------------
TONE_RULES = {
    "Professional Corporate Tone": {
        "instruction": "Formal, concise, polished, professional. No contractions, no emojis. Emphasize credibility, ROI and outcomes.",
        "cta": "Let me know if you'd like a sample."
    },
    "Friendly Conversational Tone": {
        "instruction": "Warm, friendly, conversational. Use contractions and light personalization. Keep phrasing approachable.",
        "cta": "Happy to share a sample if you'd like — shall I send one?"
    },
    "Insight-Driven Consultative Tone": {
        "instruction": "Authoritative and consultative. Add one short industry insight sentence (1 sentence max) that highlights a pain point or trend and how data helps.",
        "cta": "Would a sample list help you evaluate fit for your targets?"
    },
    "Action-Oriented Urgency Tone": {
        "instruction": "Direct, short sentences with urgency. Use action verbs and a time-sensitive CTA (e.g., 'today', 'now').",
        "cta": "I can send a sample today — should I share it now?"
    }
}

# -------------------------
# Email generation (locked format)
# -------------------------
def generate_email(url, scraped_text, tone_label, company_summary, industry, icps, solutions):
    tone_info = TONE_RULES.get(tone_label, {})
    tone_instruction = tone_info.get("instruction", tone_label)
    cta_line = tone_info.get("cta", "Let me know if you'd like a sample.")
    # Choose three ICP lines (guarantee three)
    icp_lines = (icps + ["Decision Maker A", "Decision Maker B", "Decision Maker C"])[:3]
    solutions_text = ", ".join(solutions) if isinstance(solutions, list) and solutions else "your services"
    # Build explicit prompt that forces format and tone changes
    prompt = f"""
You are a senior B2B email copywriter.

Follow these strict rules:
1) Output EXACTLY one email in the format shown below; do NOT output anything else.
2) Maintain the exact structural format and bullet layout. You may only change the wording in the allowed parts.
3) Use the tone instruction provided and craft a subject line that matches the tone.

Tone instruction: {tone_instruction}

EMAIL FORMAT (use exactly this structure - replace placeholders below with natural language):
Subject: <one-line subject>

Hello [First Name],

We offer targeted email lists to help you connect with:
• {icp_lines[0]}
• {icp_lines[1]}
• {icp_lines[2]}

Perfect if you offer services like {solutions_text} in the {industry} industry.

{cta_line}

{STATIC_SIGNATURE}

Company URL: {url}
Company Summary: {company_summary}
Scraped Content: {scraped_text}
"""
    body = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.6,
        "max_tokens": 700
    }
    res = safe_post(body)
    if res is None or "error" in res:
        return f"⚠️ API Error: {res.get('error') if isinstance(res, dict) else res}"
    try:
        return res["choices"][0]["message"]["content"]
    except Exception as e:
        return f"⚠️ Parsing Error: {e}"

# -------------------------
# Parse Subject + Body
# -------------------------
def parse_subject_and_body(email_text):
    subj = ""
    body = ""
    if not email_text:
        return subj, body
    lines = email_text.splitlines()
    for i, line in enumerate(lines):
        if line.lower().startswith("subject:"):
            subj = line.split(":", 1)[1].strip()
            body = "\n".join(lines[i+1:]).strip()
            break
    if not subj:
        # fallback: first non-empty line is subject
        for line in lines:
            if line.strip():
                subj = line.strip()
                break
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
    return subj, body

# -------------------------
# Single URL Mode
# -------------------------
def analyze_single_url():
    st.header("Single URL Analysis")
    url = st.text_input("Enter Website URL:")
    if st.button("Analyze"):
        if not url:
            st.error("Please enter a URL")
            return

        st.info("Scraping website content...")
        scraped = scrape_website(url)
        st.info("Generating structured insights...")
        insights = generate_insights(url, scraped)

        if not insights:
            st.warning("Could not extract structured insights reliably. Using fallback defaults.")
            insights = {
                "company_summary": "A growing organization operating in its industry.",
                "ideal_customers": ["Decision Maker A", "Decision Maker B", "Decision Maker C", "Decision Maker D", "Decision Maker E"],
                "solutions": ["operational efficiency", "compliance support"],
                "industry": "Industry"
            }

        company_summary = insights.get("company_summary", "")
        ideal_customers = insights.get("ideal_customers", [])
        solutions = insights.get("solutions", [])
        industry = insights.get("industry", "Industry")

        st.subheader("📌 Company Insights (extracted)")
        st.json(insights)

        st.subheader("✉️ Generated Emails (4 distinct tones)")
        tone_labels = [
            "Professional Corporate Tone",
            "Friendly Conversational Tone",
            "Insight-Driven Consultative Tone",
            "Action-Oriented Urgency Tone"
        ]

        email_outputs = {}
        with st.spinner("Generating emails..."):
            for t in tone_labels:
                email_outputs[t] = generate_email(url, scraped, t, company_summary, industry, ideal_customers, solutions)
                # small delay to reduce risk of rate limit
                time.sleep(0.3)

        for t in tone_labels:
            subj, body = parse_subject_and_body(email_outputs[t])
            st.subheader(t)
            st.text_area(f"{t} — Copy & Paste", f"Subject: {subj}\n\n{body}", height=300)

# -------------------------
# Bulk CSV Mode
# -------------------------
def analyze_bulk_mode():
    st.header("Bulk CSV Upload")
    uploaded = st.file_uploader("Upload a CSV with a column named 'url'", type=["csv"])
    if uploaded is None:
        st.info("Upload a CSV to run bulk analysis. CSV must contain a column named 'url'.")
        return

    try:
        df = pd.read_csv(uploaded)
    except Exception as e:
        st.error(f"Failed to read CSV: {e}")
        return

    if "url" not in df.columns:
        st.error("CSV must contain a column named 'url'")
        return

    if st.button("Run Bulk Analysis"):
        results = []
        progress = st.progress(0)
        total = len(df)
        tone_labels = [
            "Professional Corporate Tone",
            "Friendly Conversational Tone",
            "Insight-Driven Consultative Tone",
            "Action-Oriented Urgency Tone"
        ]

        for idx, row in df.iterrows():
            url = row.get("url", "")
            scraped = scrape_website(url)
            insights = generate_insights(url, scraped)
            if not insights:
                insights = {
                    "company_summary": "A growing organization operating in its industry.",
                    "ideal_customers": ["Decision Maker A", "Decision Maker B", "Decision Maker C", "Decision Maker D", "Decision Maker E"],
                    "solutions": ["operational efficiency", "compliance support"],
                    "industry": "Industry"
                }

            company_summary = insights.get("company_summary", "")
            ideal_customers = insights.get("ideal_customers", [])
            solutions = insights.get("solutions", [])
            industry = insights.get("industry", "Industry")

            entry = {"url": url, "company_summary": company_summary, "industry": industry}
            for t in tone_labels:
                email_text = generate_email(url, scraped, t, company_summary, industry, ideal_customers, solutions)
                subj, body = parse_subject_and_body(email_text)
                key_sub = f"{t.replace(' ', '_').lower()}_subject"
                key_body = f"{t.replace(' ', '_').lower()}_body"
                entry[key_sub] = subj
                entry[key_body] = body
                time.sleep(0.25)

            results.append(entry)
            progress.progress((idx + 1) / total)

        result_df = pd.DataFrame(results)
        st.success("Bulk processing complete!")
        st.dataframe(result_df)

        csv_bytes = result_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download Results CSV", csv_bytes, "email_results.csv", "text/csv")

# -------------------------
# Main UI
# -------------------------
st.title("🌐 Website Outreach AI Agent (Groq) — Final")
st.write("All features active: Single URL, Bulk CSV, JSON insights, and 4 distinct tones (A: long names).")

mode = st.radio("Select Mode", ["Single URL", "Bulk CSV Upload"], index=0)
if mode == "Single URL":
    analyze_single_url()
else:
    analyze_bulk_mode()
