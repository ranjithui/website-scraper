# -------------------------
# Streamlit UI
# -------------------------
st.title("🌐 Website Outreach AI Agent (Groq)")

mode = st.radio("Select Mode", ["Single URL", "Bulk CSV Upload"])

# -------------------------
# Basic Analysis Function
# -------------------------
def groq_ai_basic_analysis(url, text):
    prompt = f"""
You are a helpful business analyst AI.

Task: Based on the website URL and its content, provide a **short summary of the company** including:
- Company name (if found)
- Industry or sector
- Brief description of products/services
- Likely target audience

Website: {url}

Scraped Content:
{text}

Keep it concise, 4-6 sentences max.
"""
    body = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5
    }

    try:
        r = requests.post(API_URL, headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }, json=body)

        response = r.json()
        choices = response.get("choices", [])
        if not choices:
            return f"❌ Groq API Unexpected Response: {json.dumps(response, indent=2)}"

        return choices[0]["message"]["content"]

    except Exception as e:
        return f"⚠️ API Error: {e}"

# -------------------------
# Single URL Analysis
# -------------------------
def analyze_single_url():
    url = st.text_input("Enter Website URL:")
    if st.button("Analyze"):
        if url:
            text = scrape_website(url)
            st.subheader("📌 Generating Analysis & Emails... Please wait.")

            # -------------------------
            # Basic Company Analysis
            # -------------------------
            analysis = groq_ai_basic_analysis(url, text)
            st.subheader("📊 Basic Company Analysis")
            st.write(analysis)

            # -------------------------
            # Professional Email
            # -------------------------
            content_prof = groq_ai_analyze(url, text, "Professional")
            subject_prof, body_prof = parse_analysis(content_prof)

            # Humble & Conversational Email
            content_humble = groq_ai_analyze(url, text, "Humble & Conversational")
            subject_humble, body_humble = parse_analysis(content_humble)

            st.subheader("1️⃣ Professional Email")
            st.text_area("Copy & Paste Ready Email", f"📧 Email Subject:\n{subject_prof}\n\n📨 Email Body:\n{body_prof}", height=250)

            st.subheader("2️⃣ Humble & Conversational Email")
            st.text_area("Copy & Paste Ready Email", f"📧 Email Subject:\n{subject_humble}\n\n📨 Email Body:\n{body_humble}", height=250)

# -------------------------
# Bulk CSV Analysis (unchanged)
# -------------------------
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

                # Basic Analysis
                analysis = groq_ai_basic_analysis(url, text)

                # Professional Email
                content_prof = groq_ai_analyze(url, text, "Professional")
                subject_prof, body_prof = parse_analysis(content_prof)

                # Humble & Conversational Email
                content_humble = groq_ai_analyze(url, text, "Humble & Conversational")
                subject_humble, body_humble = parse_analysis(content_humble)

                results.append({
                    "url": url,
                    "basic_analysis": analysis,
                    "professional_subject": subject_prof,
                    "professional_body": body_prof,
                    "humble_subject": subject_humble,
                    "humble_body": body_humble
                })

                progress.progress((i + 1) / len(df))

            result_df = pd.DataFrame(results)
            st.success("Bulk Analysis Completed!")
            st.dataframe(result_df)

            csv = result_df.to_csv(index=False).encode('utf-8')
            st.download_button("Download Results CSV", csv, "results.csv", "text/csv")

# -------------------------
# Mode Selection
# -------------------------
if mode == "Single URL":
    analyze_single_url()
else:
    analyze_bulk()
