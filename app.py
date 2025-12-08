import streamlit as st
import pandas as pd
import time

st.set_page_config(page_title="Bulk Website Insights Generator", layout="wide")


# ---------------------------
# Replace this with your real AI/Web scraping function
# ---------------------------
def call_api(website):
    # --- Mocked output (replace with real scraping logic if needed) ---
    return {
        "company_name": website.replace("https://", "").replace("www.", "").split(".")[0].title(),
        "company_summary": f"{website} appears to be a reputable business offering valuable services.",
        "main_products": "AI Tools, SaaS Platform, Automation Software",
        "ideal_customers": "Enterprise, SMB, Freelancers",
        "ideal_audience": "Decision Makers, CTOs, Founders",
        "industry": "Technology",
        "countries_of_operation": "Global"
    }


# ---------------------------
# Processing Function
# ---------------------------
def process_csv(df, website_column, live_output):
    results = []

    progress = st.progress(0)

    for index, row in df.iterrows():

        website = row[website_column]

        live_output.markdown(f"### 🔍 Processing: `{website}` ({index+1}/{len(df)})")

        try:
            result = call_api(website)

            # show result live
            live_output.json(result)

            combined_row = {**row.to_dict(), **result}
            results.append(combined_row)

        except Exception as e:
            live_output.error(f"❌ Error while processing {website}: {str(e)}")
            results.append({**row.to_dict(), "error": str(e)})

        # update progress bar
        progress.progress((index + 1) / len(df))

        # 20 sec delay
        time.sleep(20)

    return pd.DataFrame(results)


# ---------------------------
# UI
# ---------------------------
st.title("📄 Bulk Website Insights Generator — Live Processing Mode")

uploaded_file = st.file_uploader("📤 Upload CSV (must contain a Website/URL column)", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    st.write("📌 File Preview:")
    st.dataframe(df.head())

    # Detect website column intelligently
    website_guess = None
    for col in df.columns:
        if col.lower() in ["website", "url", "domain"]:
            website_guess = col
            break

    website_column = st.selectbox(
        "Select Website Column:",
        df.columns.tolist(),
        index=df.columns.tolist().index(website_guess) if website_guess else 0
    )

    live_output = st.empty()

    if st.button("🚀 Start Processing"):
        with st.spinner("Processing websites... Please wait ⏳"):
            final_df = process_csv(df, website_column, live_output)

        st.success("🎉 Processing Finished!")

        st.write("📌 Final Output:")
        st.dataframe(final_df)

        csv = final_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="📥 Download Results CSV",
            data=csv,
            file_name="Website_Insights_Results.csv",
            mime="text/csv"
        )
