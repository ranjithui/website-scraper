import streamlit as st
import pandas as pd
import time
import requests

st.set_page_config(page_title="Bulk Insights Generator", layout="wide")

# ---------------------------
# Functions
# ---------------------------

def call_api(company_name):
    """Simulated API call — replace with your real API logic."""
    
    # Example of what you'd send to your API
    # response = requests.post(
    #     "https://your-api-url",
    #     headers={"Authorization": f"Bearer {API_KEY}"},
    #     json={"company_name": company_name}
    # )
    #
    # return response.json()

    # ---- MOCK response for example ----
    return {
        "company_summary": f"{company_name} is a global leader in innovation.",
        "main_products": "Product A, Product B, Product C",
        "ideal_customers": "Enterprises, SMBs",
        "ideal_audience": "C-Level Executives, Tech Buyers",
        "industry": "Technology",
        "countries_of_operation": "USA, UK, India"
    }


def process_csv(df):
    results = []
    for index, row in df.iterrows():

        company = row["company_name"]
        st.write(f"Processing: **{company}** ({index+1}/{len(df)})...")

        result = call_api(company)
        time.sleep(20)  # ---- 20 second delay ----

        combined_row = {**row.to_dict(), **result}
        results.append(combined_row)

    return pd.DataFrame(results)


# ---------------------------
# UI
# ---------------------------

st.title("📄 Bulk Company Insights Generator")

uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    st.write("Uploaded File Preview 👇")
    st.dataframe(df.head())

    if st.button("🚀 Start Processing"):
        with st.spinner("Processing... Please wait ⏳"):
            result_df = process_csv(df)

        st.success("🎉 Processing Complete!")

        st.write("Preview of Final Output 👇")
        st.dataframe(result_df.head())

        csv = result_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="📥 Download Processed CSV",
            data=csv,
            file_name="processed_results.csv",
            mime="text/csv"
        )
