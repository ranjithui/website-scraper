import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import re
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
# Scrape Website Content
# -------------------------
def scrape_website(url, max_chars=4000):
    try:
        r = session.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "iframe"]):
            tag.extract()
        text = soup.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]
    except Exception as e:
        st.warning(f"Failed to scrape {url}: {e}")
        return ""

# -------------------------
# Detect industry and ICPs (fallback)
# -------------------------
INDUSTRY_MAP = {
    "mining": {"icps":["Mining operators and site managers","Fleet and transport managers","Safety and compliance officers"], "value":"compliance, fleet performance, or site support"},
    "logistics": {"icps":["Logistics managers","Transport operations heads","Warehouse managers"], "value":"route optimization, fleet tracking, or cost reduction"},
    "saas": {"icps":["VP Product","Head of Growth","CTO / Engineering Leads"], "value":"product-led growth, onboarding, or developer adoption"},
    "healthcare": {"icps":["Hospital administrators","Clinical leads","Procurement managers"], "value":"clinical workflow efficiency, sourcing, or compliance"},
    "finance": {"icps":["Financial Advisors","Wealth Managers","High Net Worth Individuals"], "value":"wealth management, financial planning, or investment solutions"}
}

def detect_industry_and_icps(text, url):
    lower = (text + " " + url).lower()
    for k, v in INDUSTRY_MAP.items():
        if k in lower or k.rstrip("s") in lower:
            return k.capitalize(), v["icps"], v["value"]
    return "B2B", ["Procurement / Purchasing Heads","Operations / Facilities Managers","IT / Program Leads"], "targeted outreach and lead generation"

# -------------------------
# Build email locally
# -------------------------
def build_email_local(tone, icps, core_value, company_name, industry):
    greeting = "Hello" if tone in ["Professional","Insight","Action"] else "Hi"
    greet_line = f"{greeting} [First Name],\n\n"
    bullets = "\n".join([f"• {role}" for role in icps])
    if tone == "Professional":
        benefit = f"\n\nPerfect if you offer services like {core_value} in the {industry} industry."
        closing = "\n\nLet me know if you'd like a sample.\n\nBest regards,\n[Your Name]"
    elif tone == "Conversational":
        benefit = f"\n\nPerfect if you offer services like {core_value} in the {industry} industry."
        closing = "\n\nLet me know if you'd like a sample.\n\nBest, [Your Name] 📈"
    elif tone == "Insight":
        benefit = f"\n\nIdeal if you offer services like {core_value} to your target audience."
        closing = "\n\nWould you like me to send a sample to review?\n\nBest, [Your Name]"
    elif tone == "Action":
        benefit = f"\n\nPerfect if you offer services like {core_value} and want to accelerate outreach in the {industry} space."
        closing = "\n\nCan I send you a quick sample today?\n\nBest, [Your Name]"
    return f"{greet_line}We offer targeted email lists to help you connect with:\n{bullets}{benefit}{closing}"

# -------------------------
# Groq AI summary (optional)
# -------------------------
def groq_ai_generate_summary(url, text):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    prompt = f"""
You are a concise B2B outreach assistant. Output JSON only:
{{
"company_summary": "one 1-2 sentence summary",
"industry": "best-guess single word industry",
"icps": ["role1", "role2", "role3"],
"core_value": "short phrase describing what contacts need"
}}
Company URL: {url}
Website text: {text}
"""
    body = {"model": MODEL_NAME, "messages":[{"role":"user","content":prompt}], "temperature":0.25, "max_tokens":300}
    try:
        r = session.post(API_URL, headers=headers, json=body, timeout=30)
        r.raise_for_status()
        res = r.json()
        model_text = res["choices"][0]["message"]["content"]
        parsed = re.search(r"(\{(?:[^{}]|(?R))*\})", model_text, flags=re.DOTALL)
        if parsed:
            return json.loads(parsed.group(1))
        return None
    except:
        return None

# -------------------------
# UI - Single URL Mode
# -------------------------
def analyze_single_url():
    url = st.text_input("Enter Website URL:")
    if st.button("Analyze"):
        if not url:
            st.error("Please provide a URL.")
            return
        scraped = scrape_website(url)
        summary = groq_ai_generate_summary(url, scraped)
        if summary:
            company_summary = summary.get("company_summary","A growing organization")
            industry = summary.get("industry","B2B")
            icps = summary.get("icps") or []
            core_value = summary.get("core_value","targeted outreach and lead generation")
        else:
            industry, icps, core_value = detect_industry_and_icps(scraped,url)
            company_summary = f"A company operating in {industry}"

        if not icps or len(icps)<3:
            _, icps_default, core_default = detect_industry_and_icps(scraped,url)
            icps = icps_default
            core_value = core_value or core_default

        company_name = re.sub(r"https?://(www\.)?","",url).split("/")[0]

        # Professional Tone always
        prof_body = build_email_local("Professional", icps, core_value, company_name, industry)
        prof_subject = f"Targeted Email Lists for {industry} Outreach"

        st.subheader("📌 Company Insights")
        st.markdown(f"**Summary:** {company_summary}")
        st.markdown(f"**Industry:** {industry}")
        st.markdown(f"**ICP Roles:**")
        for r in icps:
            st.markdown(f"- {r}")
        st.markdown(f"**Core value:** {core_value}")

        st.subheader("1️⃣ Professional Corporate Tone")
        st.text_area("Professional", f"Subject: {prof_subject}\n\n{prof_body}", height=220)

        # Optional tones
        tone_choice = st.selectbox("Generate Additional Tone:", ["None","Friendly Conversational","Insight-Driven Consultative","Action-Oriented Urgency"])
        if tone_choice != "None":
            tone_map = {"Friendly Conversational":"Conversational","Insight-Driven Consultative":"Insight","Action-Oriented Urgency":"Action"}
            tone_key = tone_map[tone_choice]
            tone_body = build_email_local(tone_key, icps, core_value, company_name, industry)
            tone_subject = {"Conversational":f"Boost Your {industry} Outreach","Insight":f"Boost Your {industry} Outreach with Targeted Email Lists","Action":f"Unlock Targeted Leads in {industry}"}[tone_key]
            st.subheader(f"2️⃣ {tone_choice} Tone")
            st.text_area(tone_choice, f"Subject: {tone_subject}\n\n{tone_body}", height=220)

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
            results=[]
            progress=st.progress(0)
            total=len(df)
            for idx,row in df.iterrows():
                url=row["url"]
                scraped=scrape_website(url)
                summary=groq_ai_generate_summary(url,scraped)
                if summary:
                    company_summary=summary.get("company_summary","A growing organization")
                    industry=summary.get("industry","B2B")
                    icps=summary.get("icps") or []
                    core_value=summary.get("core_value","targeted outreach and lead generation")
                else:
                    industry, icps, core_value = detect_industry_and_icps(scraped,url)
                    company_summary=f"A company operating in {industry}"

                if not icps or len(icps)<3:
                    _, icps_default, core_default = detect_industry_and_icps(scraped,url)
                    icps = icps_default
                    core_value = core_value or core_default
                company_name = re.sub(r"https?://(www\.)?","",url).split("/")[0]
                prof_body = build_email_local("Professional", icps, core_value, company_name, industry)
                prof_subject = f"Targeted Email Lists for {industry} Outreach"

                # store results
                results.append({
                    "url": url,
                    "company_summary": company_summary,
                    "industry": industry,
                    "icp_1": icps[0],
                    "icp_2": icps[1],
                    "icp_3": icps[2],
                    "professional_subject": prof_subject,
                    "professional_body": prof_body
                })
                progress.progress((idx+1)/total)
            result_df=pd.DataFrame(results)
            st.success("Bulk generation completed.")
            st.dataframe(result_df)
            st.download_button("Download Results CSV", result_df.to_csv(index=False).encode("utf-8"), "email_results.csv", "text/csv")

# -------------------------
# App Layout
# -------------------------
st.title("🌐 Website Outreach AI Agent — Professional + Optional Tones")
mode=st.radio("Select Mode",["Single URL","Bulk CSV Upload"])
if mode=="Single URL":
    analyze_single_url()
else:
    analyze_bulk()
