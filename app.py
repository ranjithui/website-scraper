import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import json
import re

API_KEY = "YOUR_GROQ_API_KEY_HERE"
API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"

def scrape_text(url):
    try:
        response = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.text, "html.parser")
        text = " ".join(soup.stripped_strings)
        return re.sub(r"\s+", " ", text)
    except:
        return ""

def get_company_insights(text, url):
    prompt = f"""
    Extract company insights from the content below.
    If a field is missing, return [] or "".

    WEBSITE: {url}

    CONTENT:
    {text}

    Output JSON as exactly:

    {{
    "company_name":"",
    "company_summary":"",
    "main_products":[],
    "ideal_customers":[],
    "ideal_audience":[],
    "industry":"",
    "countries_of_operation":[]
    }}
    """

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}]
    }

    resp = requests.post(API_URL, headers=headers, json=payload)
    data = resp.json()

    try:
        response_text = data["choices"][0]["message"]["content"]
        return json.loads(response_text)
    except:
        return {}

# -----------------------------------------------
# MAIN PROCESS FLOW
# -----------------------------------------------
df = pd.read_csv("input_websites.csv")  # contains 'Website' column
results = []

for i, row in df.iterrows():
    url = row["Website"]
    print(f"Processing ({i+1}/{len(df)}): {url}")

    website_text = scrape_text(url)

    insights = get_company_insights(website_text, url)
    insights["Website"] = url  # keep original URL

    results.append(insights)

    print("Waiting 30 seconds before next website...")
    time.sleep(30)

# Save to CSV
output_df = pd.DataFrame(results)
output_df.to_csv("company_insights_output.csv", index=False)

print("🎯 Successfully processed & saved output to company_insights_output.csv")
