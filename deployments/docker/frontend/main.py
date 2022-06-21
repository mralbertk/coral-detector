import streamlit as st
import requests
import os
import glob2
import pandas as pd
import pymysql as sql
import pymysql.cursors


#   /------------------------------------------------/
#  /                    Temp Config                 /
# /------------------------------------------------/

# TODO: Refactor to environment variables
API_URL = "http://coral-detector-backend:8000"
VIEW_MODES = ("Upload Image(s)", "View Image(s)", "Export Statistics")
INPUT_RAW = "../storage/input/"
DEST_RESTORED = "../storage/restored/"
DEST_REFRAMED = "../storage/reframed/"
DEST_SEGMENTED = "../storage/segmented/"
DEST_MASKS = "../storage/masks/"
GALLERY_SELECTOR = {"Restored": DEST_RESTORED,
                    "Reframed": DEST_REFRAMED,
                    "Segmented": DEST_SEGMENTED,
                    "Masks": DEST_MASKS}
DB_HOST = "coral-detector-db"
DB_PORT = 3306
DB_USER = "coral-detector"
DB_PASSWORD = "ilikecorals"
DB_DATABASE = "coraldata"
DB_CURSOR = sql.cursors.DictCursor


#   /------------------------------------------------/
#  /               Function Definitions             /
# /------------------------------------------------/

# TODO: Refactor to module
def get_available_galleries(directory):
    """Scans all objects in a directory and generates a dictionary.

    Args:
        directory: A path to a directory to scan

    Returns:
        A dictionary of available galleries.
    """

    available_galleries = {}
    available_files = [file for file in os.listdir(directory)]
    for image_file in available_files:
        image_elements = image_file.split("-")
        image_location = image_elements[1]
        image_year = image_elements[0]
        if image_location in available_galleries.keys():
            available_galleries[image_location].add(image_year)
        else:
            available_galleries[image_location] = {image_year}
    return available_galleries


def query_island(connection, island, date):
    """Queries the SQL database.

    Args:
        connection: A mysql DB connection object
        island: A string, the name of the island to query
        date: A string representing a date

    Returns:
        A dictionary representing the query results
    """
    with connection:
        with connection.cursor() as cursor:
            sql = "SELECT * FROM coralcoverage WHERE island=%s AND year=%s"
            cursor.execute(sql, (island, date))
            result = cursor.fetchall()
    return result


def query_location(connection, island, pos):
    """Queries the SQL database.

    Args:
        connection: A mysql DB connection object
        island: A string, the name of the island to query
        pos: A string or an integer in the range of 1 to 20

    Returns:
        A dictionary representing the query results
    """
    with connection:
        with connection.cursor() as cursor:
            sql = "SELECT * FROM coralcoverage WHERE island=%s AND position=%s"
            cursor.execute(sql, (island, pos))
            result = cursor.fetchall()
    return result


def query_all(connection):
    """Queries the SQL database

    Args:
        connection: A mysql DB connection object

    Returns:
        A dictionary representing the entire database
    """
    with connection:
        with connection.cursor() as cursor:
            sql = "SELECT * FROM coralcoverage"
            cursor.execute(sql)
            result = cursor.fetchall()
    return result


#   /------------------------------------------------/
#  /                    Main Script                 /
# /------------------------------------------------/


# Title
st.header("Coral Image Processor")

# Select view mode
mode = st.selectbox("What would you like to do?", VIEW_MODES)

# Image Upload Mode ==================================
if mode == "Upload Image(s)":
    with st.form("s3_uploader"):

        # User input form
        st.subheader("Upload Image(s)")
        st.text("Note: Images will be stored as: [year]-[location]-[upload_filename]")
        location = st.text_input("Location",
                                 value="",
                                 help="Name of the Location the image(s) is/are from, i.e. Takapoto.")
        year = st.text_input("Year",
                             value="",
                             help="Year the image(s) was/were taken.")
        images = st.file_uploader("Upload File(s)", accept_multiple_files=True)
        submitted = st.form_submit_button("Upload")
        if submitted and images and location != "" and year != "":

            # Upload images & convert (currently NEF to JPG only)
            raw_imgs = []
            for image in images:
                filename = f"{INPUT_RAW}{year}-{location}-{image.name}"
                with open(filename, "wb") as f:
                    f.write(image.getbuffer())
                raw_img = requests.post(f"{API_URL}/store/{year}-{location}-{image.name}")
                raw_imgs.append(f"{INPUT_RAW}{raw_img.json()['image']}")

            # Apply image enhancement filters
            restored_imgs = []
            for raw_img in raw_imgs:
                restored_img = requests.post(f"{API_URL}/restore/?path={raw_img}")
                restored_imgs.append(f"{DEST_RESTORED}{restored_img.json()['image']}")

            # Reframe images
            reframed_imgs = []
            for restored_img in restored_imgs:
                reframed_img = requests.post(f"{API_URL}/reframe/?path={restored_img}")
                reframed_imgs.append(f"{DEST_REFRAMED}{reframed_img.json()['image']}")

            # Perform the segmentation
            for reframed_img in reframed_imgs:
                requests.post(f"{API_URL}/segment/?path={reframed_img}")

# Image view mode ====================================
if mode == "View Image(s)":

    # Scan storage directory for available images and cache result
    if 'galleries' not in st.session_state:
        st.session_state.galleries = get_available_galleries(DEST_SEGMENTED)

    # Show selector
    selector_col_1, selector_col_2, selector_col_3 = st.columns(3)

    # Select location
    with selector_col_1:
        s3_locs = st.selectbox("Location",
                               sorted([*st.session_state.galleries]))

    # Select year
    with selector_col_2:
        s3_ys = st.selectbox("Year",
                             sorted(list(st.session_state.galleries[s3_locs])))

    # Select version (restored, reframed, segmented or binary masks masks)
    with selector_col_3:
        s3_vs = st.selectbox("Version",
                             list(GALLERY_SELECTOR.keys()))

    # Fetch and display images
    btn_go = st.button("GO!")
    if btn_go:

        # Fetch images
        globber = glob2.glob(f"{GALLERY_SELECTOR[s3_vs]}{s3_ys}-{s3_locs}-*.jpg")
        images = [file for file in globber]

        # "Gallery" layout
        cols = st.columns(4)
        loc = 0

        # Display images
        for image in images:
            with cols[loc % 4]:
                st.text(image.split("/")[-1].split(".")[0])
                st.image(image)
                loc += 1

# Get statistics mode ====================================
if mode == "Export Statistics":

    db_connection = sql.connect(host=DB_HOST,
                                port=DB_PORT,
                                user=DB_USER,
                                password=DB_PASSWORD,
                                database=DB_DATABASE,
                                cursorclass=DB_CURSOR)

    # Scan storage directory for available images and cache result
    if 'galleries' not in st.session_state:
        st.session_state.galleries = get_available_galleries(DEST_SEGMENTED)

    # Query by year
    island_col_1, island_col_2 = st.columns(2)
    st.write("Query by Year")
    st.text("Returns statistics for one island at a specific year")
    with island_col_1:    # Select location
        s3_locs = st.selectbox("Island", sorted([*st.session_state.galleries]), key="year")
    with island_col_2:    # Select year
        s3_ys = st.selectbox("Year", sorted(list(st.session_state.galleries[s3_locs])))

    # Query by position
    location_col_1, location_col_2 = st.columns(2)
    st.write("Query by Position")
    st.text("Returns statistics for one position on one Island across all years")
    with location_col_1:
        s3_locs = st.selectbox("Island", sorted([*st.session_state.galleries]), key="position")
    with location_col_2:
        s3_pos = st.selectbox("Location", range(1, 21))

    # Query Buttons
    btn_col_1, btn_col_2, btn_col_3 = st.columns(3)
    with btn_col_1:
        query_btn_island = st.button("Query by year")
    with btn_col_2:
        query_btn_position = st.button("Query by position")
    with btn_col_3:
        query_btn_all = st.button("Query all data")

    if query_btn_island or query_btn_position or query_btn_all:

        if query_btn_island:
            result = query_island(db_connection, s3_locs, s3_ys)

        if query_btn_position:
            result = query_location(db_connection, s3_locs, s3_pos)

        if query_btn_all:
            result = query_all(db_connection)

        # Prepare CSV download file
        result_frame = pd.DataFrame(result)
        if not result_frame.empty:
            result_frame.sort_values(['island', 'year', 'position'], inplace=True)
        st.dataframe(result_frame)  # TODO: Fix bug - leading & trailing zeroes are removed
        result_csv = result_frame.to_csv().encode('utf-8')
        btn_load_csv = st.download_button(
            "Download Data",
            result_csv,
            "coral_export.csv",
            "text/csv"
        )
