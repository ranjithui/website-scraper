import streamlit as st
import pandas as pd
import time
import requests

st.set_page_config(page_title="Bulk Website Insights Generator", layout="wide")

# ---------------------------
# Mock API Function (Replace with your real API call)
# ---------------------------
def call_api(website):
    # Replace with real API call here
    # response = requests.post(...)
    # return response.json()

    return {
        "company_name": website.replace("https://", "").replace("www.", "").split(".")[0].title(),
        "company_summary": f"{website} appears to be a leading business in its category.",
        "main_products": "Product A, Product B",
        "ideal_customers": "Enterprise, SMB",
        "ideal_audience": "Decision makers, C-Level",
        "industry": "Unknown (auto-detect in real API)",
        "countries_of_operation": "Global"
    }


# ---------------------------
# Processing Function
# ---------------------------
def process_csv(df, website_column):
    results = []

    for index, row in df.iterrows():
        website = row[website_column]

        st.write(f"🌐 Processing website: **{website}** ({index+1}/{len(df)})...")

        result = call_api(website)

        combined_row = {**row.to_dict(), **result}
        results.append(combined_row)

        time.sleep(20)  # Delay between rows

    return pd.DataFrame(results)


# ---------------------------
# UI
# ---------------------------
st.title("📄 Bulk Website Insights Generator")

uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    st.write("📌 Uploaded File Preview:")
    st.dataframe(df.head())

    # Detect Website column automatically
    website_col_guess = None
    for col in df.columns:
        if col.lower() == "website" or "url" in col.lower() or "domain" in col.lower():
            website_col_guess = col
            break

    # Allow user to confirm or change
    website_column = st.selectbox(
        "Select the column containing Website URLs",
        df.columns.tolist(),
        index=df.columns.tolist().index(website_col_guess) if website_col_guess in df.columns else 0
    )

    if st.button("🚀 Start Processing"):
        with st.spinner("Processing websites... please wait ⏳"):
            result_df = process_csv(df, website_column)

        st.success("🎉 Processing Complete!")

        st.write("📌 Final Output Preview:")
        st.dataframe(result_df.head())

        csv = result_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="📥 Download Results CSV",
            data=csv,
            file_name="processed_website_insights.csv",
            mime="text/csv"
        )
