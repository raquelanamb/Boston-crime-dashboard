import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import altair as alt

# streamlit setup:
st.set_page_config(page_title="Boston Crime Insights", layout="wide")
st.title("🚔 Boston Crime Dashboard — 2023 to Present")

# Boston dataset API (updated daily):
RESOURCE_ID = "b973d8cb-eeb2-4e7e-99da-c92938efc9c0"
API_URL = f"https://data.boston.gov/api/3/action/datastore_search?resource_id={RESOURCE_ID}&limit=500000"


# load live data (cached hourly):
@st.cache_data(ttl=3600, show_spinner=True)
def load_data():
    r = requests.get(API_URL).json()
    df = pd.DataFrame(r["result"]["records"])
    
    # cleaning & typing:
    df["OCCURRED_ON_DATE"] = pd.to_datetime(df["OCCURRED_ON_DATE"], errors="coerce")
    df["YEAR"] = df["OCCURRED_ON_DATE"].dt.year
    df["MONTH"] = df["OCCURRED_ON_DATE"].dt.month
    df["HOUR"] = pd.to_numeric(df["HOUR"], errors="coerce")
    df["SHOOTING"] = df["SHOOTING"].fillna("0").replace({"Y": "1"}).astype(int)
    
    return df


df = load_data()

# sidebar filters:
st.sidebar.header("Filters")
years = sorted(df["YEAR"].dropna().unique(), reverse=True)
year_filter = st.sidebar.multiselect("Year", years, default=years)

crime_types = sorted(df["OFFENSE_DESCRIPTION"].dropna().unique())
crime_filter = st.sidebar.multiselect("Crime Types", crime_types[:40])

districts = sorted(df["DISTRICT"].dropna().unique())
dist_filter = st.sidebar.multiselect("Police Districts", districts)

# apply filters:
df_f = df.copy()
if year_filter:
    df_f = df_f[df_f["YEAR"].isin(year_filter)]
if crime_filter:
    df_f = df_f[df_f["OFFENSE_DESCRIPTION"].isin(crime_filter)]
if dist_filter:
    df_f = df_f[df_f["DISTRICT"].isin(dist_filter)]


# summary KPIs:
st.subheader("Key Metrics")

col1, col2, col3, col4 = st.columns(4)

col1.metric("Total Records", f"{len(df_f):,}")
col2.metric("Incidents This Month", f"{len(df_f[df_f['MONTH'] == datetime.now().month]):,}")
col3.metric("Shooting Incidents", df_f["SHOOTING"].sum())
col4.metric("Unique Districts", df_f["DISTRICT"].nunique())


# time series - crime volume:
st.subheader("Crime Volume Over Time")

ts = (
    df_f
    .set_index("OCCURRED_ON_DATE")
    .resample("D")
    .size()
    .rename("count")
    .reset_index()
)

line = alt.Chart(ts).mark_line().encode(
    x="OCCURRED_ON_DATE:T",
    y="count:Q"
).properties(height=300)

st.altair_chart(line, use_container_width=True)


# heatmap: crime by hour & day:
st.subheader("Crime Heatmap: Hour vs Day of Week")

df_f["DAY_OF_WEEK"] = df_f["OCCURRED_ON_DATE"].dt.day_name()

heat = (
    df_f.groupby(["DAY_OF_WEEK", "HOUR"])
    .size()
    .reset_index(name="count")
)

heatmap = alt.Chart(heat).mark_rect().encode(
    x=alt.X("HOUR:O", title="Hour of Day"),
    y=alt.Y("DAY_OF_WEEK:O", sort=[
        "Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"
    ]),
    color=alt.Color("count:Q", scale=alt.Scale(scheme="reds"))
).properties(height=300)

st.altair_chart(heatmap, use_container_width=True)


# top offenses (bar chart):
st.subheader("Top 20 Crimes")

top_crimes = (
    df_f["OFFENSE_DESCRIPTION"]
    .value_counts()
    .head(20)
    .reset_index()
    .rename(columns={"index": "Crime", "OFFENSE_DESCRIPTION": "Count"})
)

bar1 = alt.Chart(top_crimes).mark_bar().encode(
    x="Count:Q",
    y=alt.Y("Crime:N", sort="-x")
).properties(height=500)

st.altair_chart(bar1, use_container_width=True)


# district activity:
st.subheader("Crime by Police District")

dist = (
    df_f["DISTRICT"]
    .value_counts()
    .reset_index()
    .rename(columns={"index": "District", "DISTRICT": "Count"})
)

bar2 = alt.Chart(dist).mark_bar().encode(
    x="Count:Q",
    y=alt.Y("District:N", sort="-x")
)

st.altair_chart(bar2, use_container_width=True)


# shooting analysis:
st.subheader("Shooting Incidents Timeline")

shoot = (
    df_f[df_f["SHOOTING"] == 1]
    .set_index("OCCURRED_ON_DATE")
    .resample("W")
    .size()
    .rename("shootings")
    .reset_index()
)

shoot_line = alt.Chart(shoot).mark_line(color="red").encode(
    x="OCCURRED_ON_DATE:T",
    y="shootings:Q"
).properties(height=250)

st.altair_chart(shoot_line, use_container_width=True)


# raw table:
st.subheader("📄 Raw Data (Filtered)")
st.dataframe(df_f.head(500))
