import logging
import streamlit as st
from PIL import Image
from botocore.exceptions import ClientError
import boto3
from components.Parameter_store import S3_BUCKET_NAME

assignments_table_name = "assignments"
dynamodb = boto3.resource("dynamodb")
assignments_table = dynamodb.Table(assignments_table_name)


# create a function to retrieve records from DynamoDB table and return a list of records
def get_records_from_dynamodb():
    response = assignments_table.scan()
    return response["Items"]


#  create a function to download images from s3 bucket
def download_image(image_name, file_name):
    s3 = boto3.client("s3")
    try:
        s3.download_file(S3_BUCKET_NAME, image_name, file_name)
        return True
    except ClientError as e:
        logging.error(e)
        return False


# Page configuration
st.set_page_config(page_title="Show Assignment",  page_icon=":bar_chart:", layout="wide")

# Rest of the page
st.markdown("# Selected Assignment")
st.sidebar.header("Show Assignments")

# add a list of prompts from DynamoDB
db_records = get_records_from_dynamodb()
prompts = [record["assignment_id"] for record in db_records]

prompt_option = st.sidebar.selectbox("Select an assignment", prompts)

if prompt_option:
    for record in db_records:
        if record["assignment_id"] == prompt_option:
            prompt_selection = record

    image_name = prompt_selection["s3_image_name"]
    file_name = "temp-show.png"
    if download_image(image_name, file_name):
        st.image(Image.open(file_name), width=128)
    else:
        st.write("Image not found")

    st.write(prompt_selection["prompt"])
    st.text_area("", prompt_selection["question_answers"], height=320)

hide_streamlit_style = """
    <style>
        #MainMenu {visibility: hidden;}
        footer{ visibility: hidden;}
    </style>
    """

st.markdown(hide_streamlit_style, unsafe_allow_html=True)
