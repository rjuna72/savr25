import streamlit as st
import pandas as pd
import numpy as np

# Generate fake data with a leak
dates = pd.date_range("2024-06-01", periods=1440, freq="T")
flow = np.random.normal(5, 1, 1440)  # Normal usage (5L/min)
flow[500:600] = 20  # Add a 1-hour leak
df = pd.DataFrame({"timestamp": dates, "flow_Lmin": flow})

# Detect leaks (simple threshold)
df["leak"] = df["flow_Lmin"] > 15

# Streamlit UI
st.title("LeakLocker QLD 💧")
st.line_chart(df.set_index("timestamp")["flow_Lmin"])
st.write(f"🚨 **Leaks detected:** {df['leak'].sum()}")
if df['leak'].any():
    st.error("Text alert sent to homeowner: 'Leak detected!'")