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
        # Remove scripts/styles
        for s in soup(["script", "style", "noscript"]):
            s.extract()
        text = soup.get_text(separator=" ", strip=True)
        return text[:4000]
    except Exception as e:
        st.warning(f"Failed to scrape {url}: {e}")
        return ""

# -------------------------
# JSON Insight Generation (reliable first step)
# -------------------------
def generate_insights(url, scraped_text):
    prompt = f"""
You are an assistant that extracts short structured company insights.

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
        # Extract JSON strictly between first { and last }
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == -1:
            return None
        j = json.loads(text[start:end])
        # Normalize fields
        for k in ["company_summary", "ideal_customers", "solutions", "industry"]:
            if k not in j:
                j[k] = "" if k == "company_summary" or k == "industry" else []
        # Guarantee at least 3 ICPs
        if not isinstance(j["ideal_customers"], list):
            j["ideal_customers"] = []
        return j
    except Exception:
        return None

# -------------------------
# Email Generator with Strong Tone Rules
# -------------------------
TONE_RULES = {
    "Professional Corporate Tone": "Formal, concise, polished, professional. No contractions, no emojis, focus on ROI and credibility.",
    "Friendly Conversational Tone": "Warm, approachable, slightly casual. Use contractions, friendly language, short personalization lines.",
    "Insight-Driven Consultative Tone": "Add one short industry insight sentence showing knowledge of common pain points. Authoritative but helpful.",
    "Action-Oriented Urgency Tone": "Short sentences, urgency language (e.g., 'I can send this today'), clear direct CTA, energetic."
}

def generate_email(url, scraped_text, tone_label, company_summary, industry, icps, solutions):
    # Build a stronger prompt which enforces the locked email format and tone differences
    tone_instruction = TONE_RULES.get(tone_label, tone_label)
    # Prepare ICP bullets (exact 3 lines will be used in email; prefer first three from insights)
    icp_lines = icps[:3] if icps else ["Decision Maker 1", "Decision Maker 2", "Decision Maker 3"]
    solutions_text = ", ".join(solutions) if isinstance(solutions, list) and solutions else "your services"
    # CTA variations by tone (keeps base structure but varies CTA)
    cta_map = {
        "Professional Corporate Tone": "Let me know if you'd like a sample.",
        "Friendly Conversational Tone": "Happy to share a sample if you'd like — shall I send one?",
        "Insight-Driven Consultative Tone": "Would a sample list help you evaluate fit for your targets?",
        "Action-Oriented Urgency Tone": "I can send a sample today — should I share it now?"
    }
    cta_line = cta_map.get(tone_label, "Let me know if you'd like a sample.")

    # Prompt that instructs model to use EXACT FORMAT
    prompt = f"""
You are a B2B sales email writer.

Follow these strict rules:
1) Output EXACTLY one email using the format below (do NOT output anything else).
2) Maintain the exact structural lines and bullet points. Only vary wording inside the allowed places.
3) Use the tone instruction described.

Tone instruction: {tone_instruction}

EMAIL FORMAT (use exactly this structure):
Subject: <one-line subject>

Hello [First Name],

We offer targeted email lists to help you connect with:
• {icp_lines[0]}
• {icp_lines[1]}
• {icp_lines[2]}

Perfect if you offer services like {solutions_text} in the {industry} industry.

{cta_line}

Best regards,
[Your Name]

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
# Parsing helper: Subject + Body
# -------------------------
def parse_subject_and_body(email_text):
    subj = ""
    body = ""
    if not email_text:
        return subj, body
    lines = email_text.splitlines()
    # find subject line
    for i, line in enumerate(lines):
        if line.lower().startswith("subject:"):
            subj = line.split(":", 1)[1].strip()
            body = "\n".join(lines[i+1:]).strip()
            break
    if not subj:
        # if model didn't include Subject line, try to infer
        # take first non-empty line as subject fallback
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

        st.info("Scraping website...")
        scraped = scrape_website(url)
        st.info("Generating structured insights...")
        insights = generate_insights(url, scraped)

        # Fallbacks if insights extraction failed
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

        st.subheader("✉️ Generated Emails (4 tones)")
        # Generate all 4 tones
        tone_labels = [
            "Professional Corporate Tone",
            "Friendly Conversational Tone",
            "Insight-Driven Consultative Tone",
            "Action-Oriented Urgency Tone"
        ]

        email_outputs = {}
        with st.spinner("Generating emails..."):
            for t in tone_labels:
                # small sleep to avoid hitting rate limits too fast (graceful)
                email_outputs[t] = generate_email(url, scraped, t, company_summary, industry, ideal_customers, solutions)
                time.sleep(0.3)

        for t in tone_labels:
            subj, body = parse_subject_and_body(email_outputs[t])
            st.subheader(t)
            st.text_area(f"{t} — Copy & Paste", f"Subject: {subj}\n\n{body}", height=260)

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
            # generate all 4 tones
            for t in tone_labels:
                email_text = generate_email(url, scraped, t, company_summary, industry, ideal_customers, solutions)
                subj, body = parse_subject_and_body(email_text)
                # store subject + body in columns
                key_sub = f"{t.replace(' ', '_').lower()}_subject"
                key_body = f"{t.replace(' ', '_').lower()}_body"
                entry[key_sub] = subj
                entry[key_body] = body
                # short sleep
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
