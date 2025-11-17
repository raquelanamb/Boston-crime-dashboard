# Boston Crime Insights
An interactive data visualization dashboard that explores over a decade of Boston Police Department incident reports (2015–present). The project automates data collection, cleaning, and visualization to make civic crime data more accessible, transparent, and actionable.
----

**Features**
- Dynamic Filtering: Instantly filter incidents by Year, Crime Type, or Police District.
- Interactive Visualizations: Explore Boston’s crime patterns through time-series charts, heatmaps, and a district-level map built with Altair.
- Automated Updates: The dataset refreshes automatically via the Boston Open Data API whenever the app is accessed, ensuring up-to-date insights.
- Smart CSV Export: Download filtered datasets directly from the dashboard (up to 1 million rows per export).
- Lightweight Design: Optimized for performance using Streamlit caching, allowing large-scale analysis without heavy backend infrastructure.

**Overview**

Boston Crime Insights integrates a full ETL + visualization pipeline:
- Extraction: Historical CSVs (2015–present) stored on Oracle Cloud and live data from the Boston Open Data API.
- Transformation: Automatic cleaning, normalization, and type correction of fields (dates, coordinates, and categorical labels).
- Loading: Combined into a unified DataFrame for analysis and visualization.
- Visualization: Streamlit dashboard with interactive components built using Altair.
This workflow enables near real-time exploration of trends in crime volume, type distribution, temporal patterns, and geographic concentration.

**Dataset**

Source: Boston Police Department Incident Reports
- Records from 2015–present
- Updated daily via the city’s open data API
- Includes fields such as OFFENSE_DESCRIPTION, DISTRICT, YEAR, MONTH, DAY_OF_WEEK, HOUR, LAT, and LONG

**Tech Stack**
- Python 3.12
- Streamlit - dashboard framework
- Pandas – data handling and transformation
- Altair – interactive visualizations
- Requests – API data ingestion
- Oracle Cloud Object Storage – hosting of historical CSVs

**Dashboard Preview**
(Add a screenshot here ![Dashboard Screenshot](images/dashboard.png))

**Running Locally**
# 1. Clone the repository
git clone https://github.com/<your-username>/boston-crime-insights.git
cd boston-crime-insights

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
streamlit run app.py

**Deployment**
The app is deployed via Streamlit Cloud, which automatically runs the latest version of the code from this repository.
Data updates occur dynamically upon user access, ensuring near real-time accuracy.

**References**
- Boston Open Data Portal – Crime Incident Reports
- CKAN Datastore API Documentation
- Streamlit Documentation
- Altair Documentation
