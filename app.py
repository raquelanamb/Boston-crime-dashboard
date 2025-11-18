import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import altair as alt


# configure page title, layout width, & header text:
st.set_page_config(page_title="Boston Crime Insights", layout="wide")

# display title & subtitle:
st.title("Boston Crime Insights")
st.subheader("(Explore official BPD data crime incident reports from 2015 to present)")

# -------------------------------------------------------------------------------------------------------

# dataset resource ID for BPD incident reports:
RESOURCE_ID = "b973d8cb-eeb2-4e7e-99da-c92938efc9c0"

# construct API URL to retrieve <=500,000 records in JSON format:
API_URL = f"https://data.boston.gov/api/3/action/datastore_search?resource_id={RESOURCE_ID}&limit=500000"

# -------------------------------------------------------------------------------------------------------

# decorator func to cache load_data() results so Streamlit remembers it for 1 hr (3600 secs):
@st.cache_data(ttl=3600, show_spinner=True, max_entries=1, persist=True) # also set max cached versions = 1, save to disk

# loads, cleans, & merges Boston crime data from Oracle Cloud bucket + Boston’s live Data API, returns singular cleaned df:
def load_data():

    # URL for Oracle bucket boston-crime-data & files to be fetched:
    base_url = "https://idtjzemdsv58.objectstorage.us-ashburn-1.oci.customer-oci.com/n/idtjzemdsv58/b/boston-crime-data/o/"
    files = [
        "2015.csv", "2016.csv", "2017.csv", "2018.csv", "2019.csv",
        "2020.csv", "2021.csv", "2022.csv", "2023-present.csv"
    ]

    # to store yearly dfs:
    dfs = []

    # load all yearly files from Oracle Cloud:
    for fname in files:

        # create object-specific url:
        url = f"{base_url}{fname}"

        # read each CSV directly from the cloud into a df:
        try:
            df_y = pd.read_csv(url)

            # standardize column names:
            df_y.columns = df_y.columns.str.strip().str.upper()

            # append this year’s data to the list:
            dfs.append(df_y)
            # st.write(f"Loaded {fname}")
        
        # if file fails to load:
        except Exception as e:
            st.warning(f"Could not load {fname}: {e}")

    # if no files loaded successfully, stop execution:
    if not dfs:
        st.error("No data files could be loaded from Oracle Cloud.")
        st.stop()

    # combine all yearly dfs into 1 master df:
    df = pd.concat(dfs, ignore_index=True)

    # some 'OCCURRED_ON_DATE' values contain timezone suffixes (e.g., +00:00). removing them to avoid parsing errors:
    df["OCCURRED_ON_DATE"] = (
        df["OCCURRED_ON_DATE"]
        .astype(str) # converts every val in this column into str
        .str.replace(r"\+00(:00)?", "", regex=True) # remove any +00 or +00:00 suffixes from the timestamp strings
        .str.strip()
    )

    # convert date column from str vals to actual datetime objects:
    df["OCCURRED_ON_DATE"] = pd.to_datetime( # transform column into something Pandas understands as time data
        df["OCCURRED_ON_DATE"], 
        errors="coerce", # if val cannot be parsed, replace w/ NaT (not a time)
        infer_datetime_format=True, # guess date format automatically based on 1st few rows
        utc=True) # ensures all resulting datetimes are aligned to UTC

    # extract parts of the datetime objects for new columns:
    df["YEAR"] = df["OCCURRED_ON_DATE"].dt.year
    df["MONTH"] = df["OCCURRED_ON_DATE"].dt.month
    df["HOUR"] = pd.to_numeric(df["HOUR"], errors="coerce")

    # make year column an int column that can still store NaN:
    df["YEAR"] = df["YEAR"].astype("Int64") # (nullable integer type)
    
    # normalize shooting column:
    if "SHOOTING" in df.columns:
        df["SHOOTING"] = (
            df["SHOOTING"]
            .astype(str) # converts every val in this column into str
            .str.strip()
            .replace({"Y": "1", "N": "0", "": "0", "nan": "0"}) # replaces all possible text values w/ consistent numeric strs
            .fillna("0") # replace any remaining NaN with "0"
            .astype(int) # cast cleaned strs to ints now
        )
    else:
        # if dataset has no shooting col, create one & fill w/ 0s:
        df["SHOOTING"] = 0

    # fetch newest live data from Boston's Open API:
    try:
        # fetch JSON data from provided API endpoint (by sending a GET request to the URL):
        r = requests.get(API_URL).json()

        # convert 'records' part of API response into df: 
        df_live = pd.DataFrame(r["result"]["records"])

        # standardize column names:
        df_live.columns = df_live.columns.str.strip().str.upper()

        # convert date column from str vals to actual datetime objects:
        df_live["OCCURRED_ON_DATE"] = pd.to_datetime(df_live["OCCURRED_ON_DATE"], errors="coerce")

        # extract parts of the datetime objects for new cols:
        df_live["YEAR"] = df_live["OCCURRED_ON_DATE"].dt.year
        df_live["MONTH"] = df_live["OCCURRED_ON_DATE"].dt.month
        df_live["HOUR"] = pd.to_numeric(df_live["HOUR"], errors="coerce")

        # normalize shooting column:
        df_live["SHOOTING"] = (
            df_live["SHOOTING"]
            .astype(str) # converts every val in this column into str
            .str.strip()
            .replace({"Y": "1", "N": "0", "": "0", "nan": "0"}) # replaces all possible text values w/ consistent numeric strs
            .fillna("0") # replace any remaining NaN with "0"
            .astype(int) # cast cleaned strs to ints now
        )

        # find most recent date from Oracle Cloud dataset:
        latest_date = df["OCCURRED_ON_DATE"].max()

        #  only keep records newer than the latest date (to avoid duplication):
        df_live = df_live[df_live["OCCURRED_ON_DATE"] > latest_date]

        # if new data exists, merge it into the main df (& tell user):
        if len(df_live):
            st.success(f"Added {len(df_live):,} new records from Boston live API")
            df = pd.concat([df, df_live], ignore_index=True) # ignore_index resets the row numbering so that it’s continuous

    except Exception as e:

        # if API call fails, show warning but keep the cached data:
        st.warning(f"Could not fetch live data: {e}")

    # ensure all object-type columns are strings for PyArrow serialization:
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].astype(str)

    # return final combined & cleaned df:
    return df

# get the data using the func above
# bc @st.cache_data is applied, Streamlit will reuse the cached result >= 1 hr before re-running the func
df = load_data()

# -------------------------------------------------------------------------------------------------------

# find most recent date in dataset:
last_date = df["OCCURRED_ON_DATE"].max()

# display that date in the app footer:
if pd.notnull(last_date):
    st.caption(f"Data last updated: {last_date.strftime('%B %d, %Y')}") # convert to str in "[month name] [dd], [YYYY]" format
else:
    st.caption("Data last updated: Unknown")

# -------------------------------------------------------------------------------------------------------

# sidebar section title:
st.sidebar.header("Filters")

# get all available years (dropping NaN) & sort in reverse (latest 1st):
years = sorted(df["YEAR"].dropna().unique(), reverse=True)

# create multi-select dropdown for users to choose years (default selects all years):
year_filter = st.sidebar.multiselect("Year", years, default=years)

# get all crime types & create multi-select dropdown for users to choose crimes:
crime_types = sorted(df["OFFENSE_DESCRIPTION"].dropna().unique())
crime_filter = st.sidebar.multiselect("Crime Types", crime_types[:])

# get all police districts & create multi-select dropdown for users to choose districts:
districts = sorted(df["DISTRICT"].dropna().unique())
dist_filter = st.sidebar.multiselect("Police Districts", districts)

# start from copy of full dataset so original df remains untouched:
df_f = df.copy()

# keep only selected years, crimes, & districts:
if year_filter:
    df_f = df_f[df_f["YEAR"].isin(year_filter)]
if crime_filter:
    df_f = df_f[df_f["OFFENSE_DESCRIPTION"].isin(crime_filter)]
if dist_filter:
    df_f = df_f[df_f["DISTRICT"].isin(dist_filter)]

# create a 2nd filtered copy that ignores district filters
# (bc some charts (e.g., crime by district, map) should still show citywide data)
df_f_nodist = df.copy()

# keep only selected years & crimes:
if year_filter:
    df_f_nodist = df_f_nodist[df_f_nodist["YEAR"].isin(year_filter)]
if crime_filter:
    df_f_nodist = df_f_nodist[df_f_nodist["OFFENSE_DESCRIPTION"].isin(crime_filter)]

# create 3rd filtered copy that ignores crime type filters:
df_f_nocrime = df.copy()
if year_filter:
    df_f_nocrime = df_f_nocrime[df_f_nocrime["YEAR"].isin(year_filter)]
if dist_filter:
    df_f_nocrime = df_f_nocrime[df_f_nocrime["DISTRICT"].isin(dist_filter)]

# -------------------------------------------------------------------------------------------------------

# high-level summary stats:
st.subheader("Key Metrics")

# create 4 columns horizontally for metric boxes:
col1, col2, col3, col4 = st.columns(4)

# total number of filtered records:
col1.metric("Total Records", f"{len(df_f):,}")

# how many incidents occurred in the current calendar month:
col2.metric("Incidents This Month", f"{len(df_f[df_f['MONTH'] == datetime.now().month]):,}")

# number of incidents involving shootings:
col3.metric("Shooting Incidents", df_f["SHOOTING"].sum())

# count of unique police districts in the filtered subset:
valid_districts = df_f["DISTRICT"][~df_f["DISTRICT"].isin(["Outside of", "External", "nan"])]  # exclude non-district vals
col4.metric("Unique Districts", valid_districts.nunique())

# -------------------------------------------------------------------------------------------------------

# time series line chart for crime volume:
st.subheader("Crime Volume Over Time")

# group by date (daily frequency) & count number of records per day:
ts = (
    df_f
    .set_index("OCCURRED_ON_DATE") # treat OCCURRED_ON_DATE column as index (so resample has necessary datetime indexes)
    .resample("D") # groups all rows that occurred on same day
    .size() # count rows for each of those groups
    .rename("count") # rename col returned by size() to "count"
    .reset_index() # revert back to regular indexing
)

# build an Altair line chart named line using the ts df to visualize daily crime freq:
line = (
    alt.Chart(ts) # creates a new Altair Chart object
    .mark_line() # draw data as a line
    .encode(
        x=alt.X("OCCURRED_ON_DATE:T", title="Date"), # (:T - Temporal, so Altair treats x-axis as a timeline)
        y=alt.Y("count:Q", title="Number of Incidents") # (:Q - Quantitative — so Altair uses a numeric y-axis)
    )
    .properties(height=300) # set chart height in pixels
)

# render Altair line chart, line, on the app page:
st.altair_chart(line, use_container_width=True) # and stretch chart to fill available width

# -------------------------------------------------------------------------------------------------------

# heatmap of crime by hr & day:
st.subheader("Crime Heatmap")

# create column w/ textual day-of-week names (Monday–Sunday):
df_f["DAY_OF_WEEK"] = df_f["OCCURRED_ON_DATE"].dt.day_name()

# aggregate crime counts by (day, hr) into new df heat:
heat = (
    df_f.groupby(["DAY_OF_WEEK", "HOUR"]) # group all rows sharing same combo of day & hr
    .size() # count rows in each group
    .reset_index(name="count") # rename col returned by size() to "count"
)

# build an Altair line chart named heatmap using the heat df:
heatmap = alt.Chart(heat).mark_rect().encode( # render rectangles
    x=alt.X("HOUR:O", title="Hour of Day"), # (:O - Ordinal, 0-23)
    y=alt.Y("DAY_OF_WEEK:O", # (O:, Monday-Sunday)
            title='Day of Week', 
            sort=[ # ensures days appear in logical order instead of alphabetically
                "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
    ]),
    color=alt.Color("count:Q", scale=alt.Scale(scheme="reds")) # (:Q - Quantitative, use reds to convey intensity)
).properties(height=300) # fixed height in pixels

# display heatmap on the Streamlit dashboard, scale to available page width:
st.altair_chart(heatmap, use_container_width=True)

# -------------------------------------------------------------------------------------------------------

# top offenses (bar chart):
st.subheader("Top 20 Crimes")

# group by type of offense:
top_crimes = (
    df_f["OFFENSE_DESCRIPTION"]
    .value_counts() # rank by freq, return Series
    .rename_axis("Crime") # rename the index to "Crime"
    .reset_index(name="Count") # turn it into a proper df with new col "Count" ("Crime" becomes a normal column)
    .head(20) # keep only top 20 most freq
)

# build an Altair horizontal bar chart named crime_chart using the top_crimes df:
crime_chart = (
    alt.Chart(top_crimes)
    .mark_bar() # draw bars
    .encode( 
        y=alt.Y("Crime:N", sort="-x"), # (:N - Nominal, y-axis is crime categories)
        x=alt.X("Count:Q"), # (:Q - Quantitative, x-axis in the count of each)
        tooltip=["Crime", "Count"], # display exact values when hovering
    )
)

# display bar chart on the Streamlit dashboard, scale to available page width:
st.altair_chart(crime_chart, use_container_width=True)

# -------------------------------------------------------------------------------------------------------

# shooting analysis:
st.subheader("Shooting Incidents Timeline")

# filter to only rows where shooting = 1:
shoot = df_f_nocrime[df_f_nocrime["SHOOTING"] == 1].copy()

# group weekly to count total shootings per week:
shoot = (
    shoot.set_index("OCCURRED_ON_DATE")
    .resample("W") # ("W" = weekly)
    .size() # count per week
    .rename("shootings") # rename the resampled count column created by size()
    .reset_index() # restore regular indexing
)

# build an Altair red line chart named shoot_line using the shoot df:
shoot_line = (
    alt.Chart(shoot)
    .mark_line(color="red")
    .encode(
        x=alt.X("OCCURRED_ON_DATE:T", title="Date"), # (:T - Temporal, x-axis treated as timeline)
        y=alt.Y("shootings:Q", title="Number of Shootings") # (:Q - Qualitative)
    )
    .properties(height=250) # height of chart in pixels
)

# display line chart on the Streamlit dashboard, scale to available page width:
st.altair_chart(shoot_line, use_container_width=True)

# -------------------------------------------------------------------------------------------------------

# crime by district:
st.subheader("Crime by Police District")

# count number of incidents for each district:
by_district = (
    df_f_nodist["DISTRICT"] # ignoring filter for district
    .value_counts() # rank by freq, return Series
    .rename_axis("District") # rename the index to "District"
    .reset_index(name="Count") # turn it into a proper df with new col "Count" ("District" becomes a normal column)
)

# build an Altair horizontal bar chart named district_chart using the by_district df:
district_chart = (
    alt.Chart(by_district)
    .mark_bar() # draw bars
    .encode(
        y=alt.Y("District:N", sort="-x"), # (:N - Nominal, y-axis is districts)
        x=alt.X("Count:Q"), # (:Q - Quantitative, x-axis in the crime count for each)
        tooltip=["District", "Count"], # display exact values when hovering
    )
)

# display bar chart on the Streamlit dashboard, scale to available page width:
st.altair_chart(district_chart, use_container_width=True)

# -------------------------------------------------------------------------------------------------------

# crimes + police districts map:
st.subheader("Crime Map with Police Districts")

# warn user is filtered dataset is empty:
if len(df_f_nodist) == 0:
    st.warning("No map data available for the selected filters.")
else:
    # if filtered dataset too big, downsample safely:
    if len(df_f_nodist) > 20000:
        # select random 20,000 points:
        df_map = df_f_nodist.sample(20000, random_state=42)
        st.info("(Showing a random sample of 20,000 points for performance.)")
    else:
        # just copy the district-indifferent df to use:
        df_map = df_f_nodist.copy()

    # build an Altair scatterplot chart named crime_map using the df_map df:
    crime_map = (
        alt.Chart(df_map.dropna(subset=["LAT", "LONG"])) # drop entries without coordinates
        .mark_circle(size=35, opacity=0.5) # point size
        .encode(
            longitude="LONG:Q", # (:Q - Quantitative)
            latitude="LAT:Q",
            color=alt.Color("DISTRICT:N", legend=None), # (:N - Nominal, color by district categories)
            tooltip=[ # details that show when user hovers: 
                alt.Tooltip("DISTRICT:N", title="District"),
                alt.Tooltip("OFFENSE_DESCRIPTION:N", title="Crime Type"),
                alt.Tooltip("DAY_OF_WEEK:N", title="Day of Week"),
                alt.Tooltip("HOUR:Q", title="Hour of Day"),
            ],
        )
        .properties(width="container", height=500) # adjust width based on st.altair_chart
        .interactive() # allows zooming & panning
    )

    # display bar chart on the Streamlit dashboard, scale to available page width:
    st.altair_chart(crime_map, use_container_width=True)

# -------------------------------------------------------------------------------------------------------

# display raw filtered data table:
st.subheader("Raw Data (Filtered)")

# display 1st 500 rows of currently filtered dataset:
st.dataframe(df_f.head(500))

# set 1 million row max:
MAX_DOWNLOAD_ROWS = 1000000

# if more rows than the max, then warn user, grab only the max amount:
if len(df_f) > MAX_DOWNLOAD_ROWS:
    st.warning(f"Dataset is large ({len(df_f):,} rows). Only first {MAX_DOWNLOAD_ROWS:,} will be downloaded.")
    data_to_download = df_f.head(MAX_DOWNLOAD_ROWS)

# otherwise can grab all filtered data:
else:
    data_to_download = df_f

# download button for user-filtered data:
st.download_button(
    label="Download Filtered Data (CSV)",
    data=data_to_download.to_csv(index=False), # convert data_to_download df to CSV string (without index column)
    file_name="boston_crime_filtered.csv",
    mime="text/csv" # ensures correct CSV MIME type
)

# -------------------------------------------------------------------------------------------------------

# note to user footer:
st.markdown("---")
st.markdown(
    """
    **Helpful Tips:**  
    - You can filter by any combination of **Years**, **Crime Types**, and **Police Districts**!  
    - Filtering by **Police District** does **not** affect the charts *Crime by Police District* or *Crime Map with Police Districts*. These visuals always show data for **all districts**, but they still respond to **Year** and **Crime Type** filters.  
    - Filtering by **Crime Type** does **not** affect the *Shooting Incidents Timeline* graph, but it will still respond to **Year** and **Districts** filters.
    - All other visuals (e.g., Key Metrics, Crime Volume, Heatmap, Top Crimes) will refresh automatically to match your selected filters.
    - Downloads are capped at 1 million records per request.
    """,
    unsafe_allow_html=True, # allows Streamlit to interpret HTML tags inside Markdown (safe here bc text is static, not user input)
)
