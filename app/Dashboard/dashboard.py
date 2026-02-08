import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import os

# 1. Page Configuration
st.set_page_config(page_title="HRD Dashboard", layout="wide")
st.title("🔬 HRD Analysis Dashboard")

# 2. Sidebar for Uploads
with st.sidebar:
    st.header("Upload Image")
    uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"])
    analyze_button = st.button("Analyze Image")

# 3. Backend Integration
# Pulling configuration from Streamlit Secrets (Hugging Face)
API_URL = os.getenv("API_URL", "http://localhost:8000/predict")
HF_TOKEN = os.getenv("HF_TOKEN", "")

headers = {}
if HF_TOKEN:
    headers["Authorization"] = f"Bearer {HF_TOKEN}"
    
if uploaded_file is not None and analyze_button:
    with st.spinner("Processing medical image..."):
        try:
            # Prepare the file for the POST request
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
            
            # CRITICAL FIX: Added 'headers=headers' to allow access to private Space
            response = requests.post(API_URL, files=files, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                # 4. Display Metrics
                col1, col2, col3 = st.columns(3)
                col1.metric("Cancer Count", data["cancer_count"])
                col2.metric("G2 Count", data["g2_count"])
                col3.metric("HRD Percent", f"{data['hrd_percent']}%")
                
                # 5. Visualizations
                st.divider()
                view_col, chart_col = st.columns([1, 1])
                
                with view_col:
                    st.subheader("Visualized Detection")
                    st.image(data["image_data"], use_container_width=True)
                
                with chart_col:
                    st.subheader("Statistics Chart")
                    chart_df = pd.DataFrame({
                        "Category": ["Cancer", "G2"],
                        "Count": [data["cancer_count"], data["g2_count"]]
                    })
                    fig = px.bar(chart_df, x="Category", y="Count", 
                                 color="Category", color_discrete_map={"Cancer":"red", "G2":"green"})
                    st.plotly_chart(fig, use_container_width=True)
                    
            else:
                st.error(f"Backend Error: {response.status_code} - {response.text}")
        except Exception as e:
            st.error(f"Connection Failed: {e}")
else:
    st.info("Please upload an image and click 'Analyze' to begin.")