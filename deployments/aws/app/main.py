import boto3, json
import streamlit as st
import numpy as np
import pandas as pd
from PIL import Image


#   /------------------------------------------------/
#  /               Function Definitions             /
# /------------------------------------------------/

def s3_image_upload(file, file_name, bucket, client):
    """Uploads an image file object to Amazon S3.

    Args:
        file: The file object to upload to Amazon S3
        file_name: Name under which the file will be stored
        bucket: Amazon S3 bucket the file will be uploaded to
        client: A Boto3 S3 client instance.

    Returns:
        This function has no return statement

    Raises:
        TypeError: Only .jpg, .png, .tiff and .nef files are accepted
    """
    client.upload_fileobj(file, bucket, file_name)


def get_s3_object_filters(bucket, resource):
    """Scans all objects in an S3 bucket and returns dictionary of available
    locations with corresponding years.

    Args:
        bucket: The S3 bucket to scan
        resource: A Boto3 S3 resource instance

    Returns:
        A dictionary: {loc_1: {year_1, ..., year_n}, ..., loc_n: {y1, ..., yn}}

    Raises:
        Boto3 error if the bucket name is not found on your AWS account
    """
    available_sets = {}
    bucket_resource = resource.Bucket(bucket)
    bucket_objects = [s3_object.key for s3_object in bucket_resource.objects.all()]
    for bucket_object in bucket_objects:
        this_location = bucket_object.split("-")[1]  # location
        this_year = bucket_object.split("-")[0]  # year
        if this_location in available_sets.keys():
            available_sets[this_location].add(this_year)
        else:
            available_sets[this_location] = {this_year}
    return available_sets


def fetch_s3_objects(prefix, bucket, resource):
    """Fetches a list of S3 objects from a bucket based on a prefix.

    The list is used to load all images into memory and display them.

    Args:
        prefix: A string used to filter S3 objects
        bucket: The S3 bucket to fetch the objects from
        resource: A Boto3 S3 resource instance

    Returns:
        A list of S3 objects matching the filter in the selected bucket

    Raises:
        Boto3 error if the bucket name is not found on your AWS account
    """
    return [obj.key for obj in
            resource.Bucket(bucket).objects.filter(Prefix=prefix)]


def load_s3_image(s3_object, bucket, resource):
    """Loads an image file from S3 into memory.

    Args:
        s3_object: A S3 object to load
        bucket: The S3 bucket to load the image from
        resource: A Boto3 S3 resource instance

    Returns:
        np array: Image array

    Raises:
        # TODO: Identify proper error message(s)
        TypeError (probably) if s3_object is not an image file
    """
    s3_bucket = resource.Bucket(bucket)
    s3_image_object = s3_bucket.Object(s3_object)
    response = s3_image_object.get()
    file_stream = response["Body"]
    img = Image.open(file_stream)
    return np.array(img)


def query_rds(client, rds_db, rds_cluster, rds_credentials,
              island=None, location=None, year=None):
    """Queries an RDS database for coral statistics.

    Args:
        client: A RDS-Data client object
        rds_db: A RDS database as string
        rds_cluster: A RDS cluster ARN as string
        rds_credentials: An AWS secrets ARN as string
        island: The island value to query as string
        location: The location value to query as integer
        year: The year value to query as integer

    Returns:
        A dictionary of records
    """
    select_statement = f"""
    SELECT * FROM coral_coverage
    WHERE island LIKE '{island if island else "'%'"}'
    AND location LIKE {location if location else "'%'"}
    AND year LIKE {year if year else "'%'"} 
    """

    response = client.execute_statement(
        secretArn=rds_credentials,
        database=rds_db,
        resourceArn=rds_cluster,
        sql=select_statement,
        formatRecordsAs='JSON',
        includeResultMetadata=False
    )

    return json.loads(response["formattedRecords"])


#   /------------------------------------------------/
#  /               Temp Authentication              /
# /------------------------------------------------/

# TODO: Obviously ...
def authenticate():
    if st.session_state.pwd == "password":
        st.session_state.auth = True


#   /------------------------------------------------/
#  /                   Configuration                /
# /------------------------------------------------/

# TODO: Parameterize Bucket Names
# Image Upload Bucket
s3_bucket_raw = "criobe-images-raw"

# Image View Bucket TODO: Update with segmented bucket
s3_bucket_reframed = "criobe-images-reframed"
s3_bucket_selection = {"Reframed": "criobe-images-reframed",
                       "Segmented": "criobe-images-segmented",
                       "Masks": "criobe-images-masks"}

# To keep the UI simple, users can select a desired operation
# on top of the page.
view_modes = ("Upload Image(s)", "View Image(s)", "Export Statistics")

#   /------------------------------------------------/
#  /                Streamlit Script                /
# /------------------------------------------------/

# Page Configuration
st.set_page_config(
    page_title="Coral Image Processor",
    page_icon='🐠'
)

# Initialize auth session state
if 'auth' not in st.session_state:
    st.session_state.auth = False

# Page Header
st.header("Coral Image Processor")

# Authentication
if not st.session_state.auth:
    st.session_state.pwd = st.text_input("Enter Password", value="")
    st.button("Submit", on_click=authenticate)
    st.stop()

# Select view mode
mode = st.selectbox("What would you like to do?", view_modes)

# Image upload mode
if mode == "Upload Image(s)":

    # Boto3 Client
    s3_client = boto3.client("s3")

    # Upload Form
    with st.form("s3_uploader"):
        st.subheader("Upload Image(s)")
        st.text("Note: Images will be stored as: [year]-[location]-[upload_filename]")
        location = st.text_input("Location",
                                 value="",
                                 help="Name of the Location the image(s) is/are from, i.e. Takapoto.")
        year = st.text_input("Year",
                             value="",
                             help="Year the image(s) was/were taken.")
        images = st.file_uploader("Upload File(s)", accept_multiple_files=True)
        submitted = st.form_submit_button("Upload to Amazon S3")

        # Image Upload Process
        # TODO: Add stronger validation for year & location input
        if submitted \
                and images \
                and location != "" \
                and year != "":
            upload_bar = st.progress(0.0)
            to_upload = 0
            for image in images:
                to_upload += 1 / len(images)
                upload_bar.progress(to_upload)
                # Prevents the script from breaking if files are uploaded with no extension
                # TODO: Make robust: Identify valid types /w magic number & reject rest
                if len(image.name.split(".")) > 1:
                    name_two_digits = f"{int(image.name.split('.')[0]):02d}.{image.name.split('.')[-1]}"
                else:
                    name_two_digits = f"{image.name}.jpg"
                filename = f"{year}-{location}-{name_two_digits}"
                s3_image_upload(image, filename, s3_bucket_raw, s3_client)

# Image view mode
if mode == "View Image(s)":

    # Boto3 Client
    s3_resource = boto3.resource("s3")

    # Get options for selector
    if 'galleries' not in st.session_state:  # Store in session state to avoid reloading
        st.session_state.galleries = get_s3_object_filters(s3_bucket_reframed, s3_resource)

    # Show selector
    selector_col_1, selector_col_2, selector_col_3 = st.columns(3)

    # Select location
    with selector_col_1:
        s3_locs = st.selectbox("Location", sorted([*st.session_state.galleries]))

    # Select year
    with selector_col_2:
        s3_ys = st.selectbox("Year", sorted(list(st.session_state.galleries[s3_locs])))

    # Select version
    with selector_col_3:
        s3_vs = st.selectbox("Version", list(s3_bucket_selection.keys()))

    # Fetch and display images
    btn_go = st.button("GO!")

    # Activate if button is clicked
    if btn_go:

        # Fetch image names
        s3_images = fetch_s3_objects(f"{s3_ys}-{s3_locs}",
                                     s3_bucket_selection[s3_vs],
                                     s3_resource)

        # "Gallery" layout
        cols = st.columns(4)
        loc = 0

        # Load images into memory and display
        for s3_image in s3_images:
            this_image = load_s3_image(s3_image,
                                       s3_bucket_selection[s3_vs],
                                       s3_resource)
            with cols[loc % 4]:
                st.text(s3_image.split(".")[0])
                st.image(this_image)
                loc += 1

# Get statistics mode
if mode == "Export Statistics":
    st.header("UNDER CONSTRUCTION")

    # AWS clients
    s3_resource = boto3.resource("s3")  # For query options
    rds_client = boto3.client("rds-data")

    # RDS Configuration
    db_name = "criobe_corals"
    db_cluster_arn = "arn:aws:rds:eu-west-1:950138825908:cluster:dsti-criobe-db"
    db_credentials_secret_store_arn = "arn:aws:secretsmanager:eu-west-1:950138825908:secret:rds-db-credentials/cluster-AIT5MBWGBYEYUB6C6HBFTP5GR4/dsti_criobe_app-L17eZ0"

    # Get options for selector
    if 'galleries' not in st.session_state:  # Store in session state to avoid reloading
        st.session_state.galleries = get_s3_object_filters(s3_bucket_reframed, s3_resource)

    # Show selector
    selector_col_1, selector_col_2 = st.columns(2)

    # Select location
    with selector_col_1:
        s3_locs = st.selectbox("Island", sorted([*st.session_state.galleries]))

    # Select year
    with selector_col_2:
        s3_ys = st.selectbox("Year", sorted(list(st.session_state.galleries[s3_locs])))

    query_result = query_rds(rds_client, db_name, db_cluster_arn, db_credentials_secret_store_arn,
                             island=s3_locs, year=s3_ys)

    btn_fetch = st.button("GO!")

    if btn_fetch:
        result_frame = pd.DataFrame(query_result)
        if not result_frame.empty:
            result_frame.sort_values(['island', 'location', 'year'], inplace=True)
        st.dataframe(result_frame)
        result_csv = result_frame.to_csv().encode('utf-8')
        btn_load_csv = st.download_button(
            "Download",
            result_csv,
            "coral_export.csv",
            "text/csv"
        )


