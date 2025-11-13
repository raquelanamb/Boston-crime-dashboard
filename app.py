import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import altair as alt


# streamlit setup:
st.set_page_config(page_title="Boston Crime Insights", layout="wide")
st.title("Boston Crime Dashboard")
st.subheader("(Explore official BPD data crime incident reports from 2015 to present)")

# Boston dataset API (updated daily):
RESOURCE_ID = "b973d8cb-eeb2-4e7e-99da-c92938efc9c0"
API_URL = f"https://data.boston.gov/api/3/action/datastore_search?resource_id={RESOURCE_ID}&limit=500000"


# load live data (cached hourly):
@st.cache_data(ttl=3600, show_spinner=True)
def load_data():
    base_url = "https://idtjzemdsv58.objectstorage.us-ashburn-1.oci.customer-oci.com/n/idtjzemdsv58/b/boston-crime-data/o/"
    files = [
        "2015.csv", "2016.csv", "2017.csv", "2018.csv", "2019.csv",
        "2020.csv", "2021.csv", "2022.csv", "2023-present.csv"
    ]

    dfs = []
    for fname in files:
        url = f"{base_url}{fname}"
        try:
            df_y = pd.read_csv(url)
            df_y.columns = df_y.columns.str.strip().str.upper()
            dfs.append(df_y)
            # st.write(f"✅ Loaded {fname}")
        except Exception as e:
            st.warning(f"⚠️ Could not load {fname}: {e}")

    if not dfs:
        st.error("No data files could be loaded from Oracle Cloud.")
        st.stop()

    # combine everything:
    df = pd.concat(dfs, ignore_index=True)

    # normalize date strings before parsing:
    df["OCCURRED_ON_DATE"] = (
        df["OCCURRED_ON_DATE"]
        .astype(str)
        .str.replace(r"\+00(:00)?", "", regex=True)
        .str.strip()
    )
    df["OCCURRED_ON_DATE"] = pd.to_datetime(df["OCCURRED_ON_DATE"], errors="coerce", infer_datetime_format=True, utc=True)

    df["YEAR"] = df["OCCURRED_ON_DATE"].dt.year
    df["MONTH"] = df["OCCURRED_ON_DATE"].dt.month
    df["HOUR"] = pd.to_numeric(df["HOUR"], errors="coerce")
    df["YEAR"] = df["YEAR"].astype("Int64")

    if "SHOOTING" in df.columns:
        df["SHOOTING"] = (
            df["SHOOTING"]
            .astype(str)
            .str.strip()
            .replace({"Y": "1", "N": "0", "": "0", "nan": "0"})
            .fillna("0")
            .astype(int)
        )
    else:
        df["SHOOTING"] = 0

    # fetch newest live data from Boston's open API:
    try:
        RESOURCE_ID = "b973d8cb-eeb2-4e7e-99da-c92938efc9c0"
        API_URL = f"https://data.boston.gov/api/3/action/datastore_search?resource_id={RESOURCE_ID}&limit=500000"

        r = requests.get(API_URL).json()
        df_live = pd.DataFrame(r["result"]["records"])
        df_live.columns = df_live.columns.str.strip().str.upper()

        df_live["OCCURRED_ON_DATE"] = pd.to_datetime(df_live["OCCURRED_ON_DATE"], errors="coerce")
        df_live["YEAR"] = df_live["OCCURRED_ON_DATE"].dt.year
        df_live["MONTH"] = df_live["OCCURRED_ON_DATE"].dt.month
        df_live["HOUR"] = pd.to_numeric(df_live["HOUR"], errors="coerce")

        df_live["SHOOTING"] = (
            df_live["SHOOTING"]
            .astype(str)
            .str.strip()
            .replace({"Y": "1", "N": "0", "": "0", "nan": "0"})
            .fillna("0")
            .astype(int)
        )

        # append only newer data:
        latest_date = df["OCCURRED_ON_DATE"].max()
        df_live = df_live[df_live["OCCURRED_ON_DATE"] > latest_date]

        if len(df_live):
            st.success(f"Added {len(df_live):,} new records from Boston live API")
            df = pd.concat([df, df_live], ignore_index=True)
        # else:
            # st.info("No new data found in the Boston API.")
    except Exception as e:
        st.warning(f"Could not fetch live data: {e}")

    # st.info(f"Shooting column normalized — total {df['SHOOTING'].sum():,} incidents")
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

# special version that ignores district filter but keeps others:
df_f_nodist = df.copy()
if year_filter:
    df_f_nodist = df_f_nodist[df_f_nodist["YEAR"].isin(year_filter)]
if crime_filter:
    df_f_nodist = df_f_nodist[df_f_nodist["OFFENSE_DESCRIPTION"].isin(crime_filter)]

# summary KPIs:
st.subheader("Key Metrics")

col1, col2, col3, col4 = st.columns(4)

col1.metric("Total Records", f"{len(df_f):,}")
col2.metric("Incidents This Month", f"{len(df_f[df_f['MONTH'] == datetime.now().month]):,}")
col3.metric("Shooting Incidents", df_f["SHOOTING"].sum())
col4.metric("Unique Districts", df_f["DISTRICT"].nunique())

# st.write(df.columns.tolist()) # for debugging

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

line = (
    alt.Chart(ts)
    .mark_line()
    .encode(
        x=alt.X("OCCURRED_ON_DATE:T", title="Date"),
        y=alt.Y("count:Q", title="Number of Incidents")
    )
    .properties(height=300)
)

st.altair_chart(line, use_container_width=True)


# heatmap of crime by hour & day:
st.subheader("Crime Heatmap")

df_f["DAY_OF_WEEK"] = df_f["OCCURRED_ON_DATE"].dt.day_name()

heat = (
    df_f.groupby(["DAY_OF_WEEK", "HOUR"])
    .size()
    .reset_index(name="count")
)

heatmap = alt.Chart(heat).mark_rect().encode(
    x=alt.X("HOUR:O", title="Hour of Day"),
    y=alt.Y("DAY_OF_WEEK:O", title='Day of Week', sort=[
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
    .rename_axis("Crime")
    .reset_index(name="Count")
    .head(20)
)

crime_chart = (
    alt.Chart(top_crimes)
    .mark_bar()
    .encode(
        y=alt.Y("Crime:N", sort="-x"),
        x=alt.X("Count:Q"),
        tooltip=["Crime", "Count"],
    )
)

st.altair_chart(crime_chart, use_container_width=True)


# shooting analysis:
st.subheader("Shooting Incidents Timeline")

shoot = (
    df[df["SHOOTING"] == 1]  # use full dataset, not filtered by crime type
    .copy()
)

# apply year and district filters only:
if year_filter:
    shoot = shoot[shoot["YEAR"].isin(year_filter)]
if dist_filter:
    shoot = shoot[shoot["DISTRICT"].isin(dist_filter)]

shoot = (
    shoot.set_index("OCCURRED_ON_DATE")
    .resample("W")
    .size()
    .rename("shootings")
    .reset_index()
)

shoot_line = (
    alt.Chart(shoot)
    .mark_line(color="red")
    .encode(
        x=alt.X("OCCURRED_ON_DATE:T", title="Date"),
        y=alt.Y("shootings:Q", title="Number of Shootings")
    )
    .properties(height=250)
)

st.altair_chart(shoot_line, use_container_width=True)


# district activity:
st.subheader("Crime by Police District")

if "DISTRICT" not in df.columns:
    st.error("Column DISTRICT not found in dataset.")
else:
    by_district = (
        df_f_nodist["DISTRICT"]
        .value_counts()
        .rename_axis("District")
        .reset_index(name="Count")
    )

    district_chart = (
        alt.Chart(by_district)
        .mark_bar()
        .encode(
            y=alt.Y("District:N", sort="-x"),
            x=alt.X("Count:Q"),
            tooltip=["District", "Count"],
        )
    )

    st.altair_chart(district_chart, use_container_width=True)


# crimes + police districts map:
st.subheader("Crime Map with Police Districts")

if "LAT" in df_f_nodist.columns and "LONG" in df_f_nodist.columns:
    
    if len(df_f_nodist) == 0:
        st.warning("No map data available for the selected filters.")
    else:
        # downsample safely
        if len(df_f_nodist) > 20000:
            df_map = df_f_nodist.sample(20000, random_state=42)
            st.info("(Showing a random sample of 20,000 points for performance.)")
        else:
            df_map = df_f_nodist.copy()

        crime_map = (
            alt.Chart(df_map.dropna(subset=["LAT", "LONG"]))
            .mark_circle(size=35, opacity=0.5)
            .encode(
                longitude="LONG:Q",
                latitude="LAT:Q",
                color=alt.Color("DISTRICT:N", legend=None),
                tooltip=[
                    alt.Tooltip("DISTRICT:N", title="District"),
                    alt.Tooltip("OFFENSE_DESCRIPTION:N", title="Crime Type"),
                    alt.Tooltip("DAY_OF_WEEK:N", title="Day of Week"),
                    alt.Tooltip("HOUR:Q", title="Hour of Day"),
                ],
            )
            .properties(width="container", height=500)
            .interactive()
        )

        st.altair_chart(crime_map, use_container_width=True)
else:
    st.warning("Latitude/Longitude columns not found in dataset.")


# raw table:
st.subheader("Raw Data (Filtered)")
st.dataframe(df_f.head(500))


# note to user footer:
st.markdown("---")
st.markdown(
    """
    **Helpful Tips:**  
    - You can filter by any combination of **Years**, **Crime Types**, and **Police Districts**!  
    - Filtering by **Police District** does **not** affect the charts *Crime by Police District* or *Crime Map with Police Districts*. These visuals always show data for **all districts**, but they still respond to **Year** and **Crime Type** filters.  
    - Filtering by **Crime Type** does **not** affect the *Shooting Incidents Timeline* graph, but it will still respond to **Year** and **Districts** filters.
    - All other visuals (e.g., Key Metrics, Crime Volume, Heatmap, Top Crimes) will refresh automatically to match your selected filters.
    """,
    unsafe_allow_html=True,
)
