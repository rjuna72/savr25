import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import folium
from streamlit_folium import folium_static
from folium.plugins import HeatMap

# Page configuration
st.set_page_config(page_title="Water Leak Detection Dashboard", layout="wide")

# Load data function
@st.cache_data
def load_data():
    try:
        df = pd.read_csv('data.csv')
        
        # Custom datetime parser
        def parse_datetime(dt_str):
            try:
                return pd.to_datetime(dt_str, format='%d/%m/%Y %I:%M:%S %p', dayfirst=True)
            except ValueError:
                try:
                    return pd.to_datetime(dt_str, format='%Y-%m-%d %H:%M:%S')
                except ValueError:
                    return pd.NaT
        
        df['timestamp'] = df['timestamp'].apply(parse_datetime)
        df = df.dropna(subset=['timestamp'])
        return df
    
    except Exception as e:
        st.error(f"Data loading failed: {str(e)}")
        st.stop()

# Process data
def detect_anomalies(df):
    df = df.copy()
    df['hour'] = df['timestamp'].dt.hour
    df['day_of_week'] = df['timestamp'].dt.dayofweek  # Monday=0, Sunday=6
    hourly_avg = df.groupby(['suburb', 'hour'])['flow_rate_lpm'].mean().reset_index()
    hourly_avg.rename(columns={'flow_rate_lpm': 'avg_flow_rate'}, inplace=True)
    df = pd.merge(df, hourly_avg, on=['suburb', 'hour'])
    df['anomaly'] = df['flow_rate_lpm'] > (2 * df['avg_flow_rate'])
    return df

# Streamlit App
st.title("🌍 Water Leak Detection Dashboard")

# Data loading
with st.spinner("Processing geospatial data..."):
    df = load_data()
    processed_df = detect_anomalies(df)

# Sidebar filters
st.sidebar.header("Filters")
selected_suburb = st.sidebar.selectbox(
    "Select Suburb",
    options=['All'] + sorted(df['suburb'].unique().tolist())
)

selected_time = st.sidebar.slider(
    "Select Hour Range",
    min_value=0, max_value=23,
    value=(6, 18)
)

# Apply filters
filtered_df = processed_df.copy()
if selected_suburb != 'All':
    filtered_df = filtered_df[filtered_df['suburb'] == selected_suburb]
filtered_df = filtered_df[filtered_df['hour'].between(selected_time[0], selected_time[1])]

# Key metrics
col1, col2, col3 = st.columns(3)
col1.metric("Avg Flow Rate", f"{filtered_df['flow_rate_lpm'].mean():.2f} L/min")
col2.metric("Total Usage", f"{filtered_df['liters_used'].sum():.2f} L")
col3.metric("Leak Incidents", filtered_df['anomaly'].sum())

# Main visualization tabs
tab1, tab2, tab3 = st.tabs(["Geographic Heatmap", "Leak Analysis", "Usage Patterns"])

with tab1:
    st.subheader("Water Usage Intensity Map")
    
    if not filtered_df.empty:
        # Create base map
        avg_lat = filtered_df['latitude'].mean()
        avg_lon = filtered_df['longitude'].mean()
        m = folium.Map(location=[avg_lat, avg_lon], zoom_start=14)
        
        # Add heatmap layer
        heat_data = filtered_df[['latitude', 'longitude', 'flow_rate_lpm']].values.tolist()
        HeatMap(heat_data, radius=15, blur=10).add_to(m)
        
        # Add leak markers
        leak_df = filtered_df[filtered_df['anomaly']]
        for idx, row in leak_df.iterrows():
            folium.Marker(
                location=[row['latitude'], row['longitude']],
                popup=f"Leak detected at {row['timestamp'].strftime('%H:%M')}",
                icon=folium.Icon(color='red', icon='exclamation-triangle', prefix='fa')
            ).add_to(m)
        
        # Add normal markers
        normal_df = filtered_df[~filtered_df['anomaly']].sample(min(50, len(filtered_df)))
        for idx, row in normal_df.iterrows():
            folium.CircleMarker(
                location=[row['latitude'], row['longitude']],
                radius=3,
                color='blue',
                fill=True,
                fill_opacity=0.6
            ).add_to(m)
        
        folium_static(m, width=1000, height=600)
    else:
        st.warning("No data to display with current filters")

with tab2:
    # Leak analysis charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Leak Frequency by Hour")
        leak_hours = filtered_df[filtered_df['anomaly']]['hour'].value_counts().sort_index()
        fig1 = px.bar(
            leak_hours,
            labels={'value': 'Leak Count', 'index': 'Hour of Day'},
            color_discrete_sequence=['red']
        )
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        st.subheader("Top Leak Locations")
        top_leaks = filtered_df[filtered_df['anomaly']].groupby('street_address').size().nlargest(5)
        fig2 = px.pie(
            top_leaks,
            names=top_leaks.index,
            values=top_leaks.values,
            hole=0.4,
            color_discrete_sequence=px.colors.sequential.Reds_r
        )
        st.plotly_chart(fig2, use_container_width=True)

with tab3:
    # Usage pattern visualization
    if selected_suburb == 'All':
        st.subheader("Water Consumption by Suburb")
        fig3 = px.bar(
            filtered_df.groupby('suburb')['liters_used'].sum().reset_index(),
            x="suburb",
            y="liters_used",
            color="suburb"
        )
    else:
        st.subheader(f"Hourly Usage Pattern in {selected_suburb}")
        fig3 = px.line(
            filtered_df.groupby('hour')['flow_rate_lpm'].mean().reset_index(),
            x="hour",
            y="flow_rate_lpm",
            markers=True
        )
    st.plotly_chart(fig3, use_container_width=True)

# Data table
if st.checkbox("Show detailed leak records"):
    st.dataframe(
        filtered_df[filtered_df['anomaly']].sort_values("timestamp", ascending=False),
        column_config={
            "timestamp": st.column_config.DatetimeColumn("Time"),
            "street_address": "Address"
        },
        height=300,
        hide_index=True
    )