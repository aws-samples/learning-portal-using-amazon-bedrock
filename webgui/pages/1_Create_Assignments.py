import json
import logging
import math
import random
import re
import time
import base64
from io import BytesIO


import boto3
import numpy as np
import streamlit as st
from PIL import Image
from botocore.exceptions import ClientError
from components.Parameter_store import S3_BUCKET_NAME

dynamodb_client = boto3.resource("dynamodb")
bedrock_client = boto3.client("bedrock-runtime", 'us-east-1')
questions_table = dynamodb_client.Table("assignments")
user_name = "Demo-user"

if "input-text" not in st.session_state:
    st.session_state["input-text"] = None

if "question_answers" not in st.session_state:
    st.session_state["question_answers"] = None

if "reading_material" not in st.session_state:
    st.session_state["reading_material"] = None

def generate_key_for_image_upload():
    # Milliseconds since epoch
    epoch = round(time.time() * 1000)
    epoch = epoch - 1670000000000
    rand_id = math.floor(random.random() * 999)
    return (epoch * 1000) + rand_id


# create a function to load a file to S3 bucket
def load_file_to_s3(file_name, object_name):
    # Upload the file
    s3_client = boto3.client("s3")
    try:
        s3_client.upload_file(file_name, S3_BUCKET_NAME, object_name)
    except ClientError as e:
        logging.error(e)
        return False
    return True


# create a function to insert a record to DynamoDB table created_images
def insert_record_to_dynamodb(
    assignment_id, prompt, s3_image_name, question_answers
):
    questions_table.put_item(
        Item={
            "assignment_id": assignment_id,
            "teacher_id": user_name,
            "prompt": prompt,
            "s3_image_name": s3_image_name,
            "question_answers": question_answers,
        }
    )


def query_generate_image_endpoint(input_text):
    seed = np.random.randint(1000)
    input_body = {
        "text_prompts": [{"text": input_text}],
        "cfg_scale": 10,
        "seed": seed,
        "steps": 50,
    }
    stable_diffusion_api_response = bedrock_client.invoke_model(
        body=json.dumps(input_body),
        modelId="stability.stable-diffusion-xl",
        accept="application/json",
        contentType="application/json",
    )
    stable_diffusion_api_response = json.loads(
        stable_diffusion_api_response.get("body").read()
    )
    stable_diffusion_images = stable_diffusion_api_response.get("artifacts")
    image = Image.open(
        BytesIO(base64.b64decode(stable_diffusion_images[0].get("base64")))
    )
    return image


def query_generate_questions_answers_endpoint(input_text):
    input_text = "Human: " + input_text + " \\n\\nUsing the above context, please generate five questions and answers you " \
                                          "could ask students about this information.\\n\\nAssistant:"
    input_body = {
        "prompt": input_text,
        "max_tokens_to_sample": 300,
        "temperature": 1,
        "top_k": 250,
        "top_p": 0.999,
        "stop_sequences": ["\n\nHuman:"],
        "anthropic_version": "bedrock-2023-05-31",
    }
    claude_qa_response = bedrock_client.invoke_model(
        modelId="anthropic.claude-v2-100k",
        contentType="application/json",
        accept="*/*",
        body=json.dumps(input_body),
    )
    response_dict = json.loads(claude_qa_response["body"].read())
    return parse_text_to_lines(response_dict['completion'])


def query_generate_text_endpoint(input_text):
    input_body = {
        "prompt": input_text,
        "numResults": 1,
        "maxTokens": 512,
        "temperature": 0.7,
        "topP": 0.5,
        "stopSequences": [],
        "countPenalty": {"scale": 0},
        "presencePenalty": {"scale": 0},
        "frequencyPenalty": {"scale": 0},
    }
    ai21_text_response = bedrock_client.invoke_model(
        modelId="ai21.j2-jumbo-instruct",
        accept="application/json",
        contentType="application/json",
        body=json.dumps(input_body),
    )
    response_dict = json.loads(ai21_text_response["body"].read())
    return response_dict['completions'][0]['data']['text']


# Parse a string of text to get a line at a time
def parse_text_to_lines(text):
    st.write(text)
    lines = text.split('\n')
    lines = [line.strip() for line in lines]
    # Loop through each line and check if it's a question
    question_answers = []
    question = None
    answer = None
    question_id = 0
    for i in range(len(lines)):
        # regular expression pattern for Q: or Q1: or Q2
        question_pattern = re.compile("Q[0-9]?:|Question[\s]?[0-9]?:|QUESTION[\s]?[0-9]?:")
        answer_pattern = re.compile("A[0-9]?:|Answer[\s]?[0-9]?:|ANSWER[\s]?[0-9]?:")
        question_match = question_pattern.search(lines[i])
        answer_match = answer_pattern.search(lines[i])
        if question_match:
            # Get the substring after the matching pattern
            question = lines[i][question_match.end() + 1:]

        if answer_match:
            # Get the substring after the matching pattern
            answer = lines[i][answer_match.end() + 1:]

        if question and answer:
            question_answer = {'id': question_id, 'question': question, 'answer': answer}
            question_answers.append(question_answer)
            question_id += 1
            question = None
            answer = None

    return question_answers


# Page configuration
st.set_page_config(page_title="Create Assignments", page_icon=":pencil:", layout="wide")

# Sidebar
st.sidebar.header("Create Assignments")

# Rest of the page
st.markdown("# Create Assignments")
st.sidebar.header("Input text to create assignments")

text = st.text_area("Input Text")
if text and text != st.session_state.get("input-text", None) and text != "None":
    try:
        image = query_generate_image_endpoint(text)
        image.save("temp-create.png")
        st.session_state["input-text"] = text

        # generate questions and answer
        questions_answers = query_generate_questions_answers_endpoint(text)
        # st.write(questions_answers)
        st.session_state["question_answers"] = questions_answers
    except Exception as ex:
        st.error(f"There was an error while generating question. {ex}")

if st.session_state.get("question_answers", None):
    st.markdown("## Generated Questions and Answers")
    questions_answers = st.text_area(
        "Questions and Answers",
        json.dumps(st.session_state["question_answers"], indent=4),
        height=320,
        label_visibility="collapsed"
    )

if st.button("Generate Questions and Answers"):
    st.session_state["question_answers"] = query_generate_questions_answers_endpoint(text)
    st.experimental_rerun()

if st.session_state.get("input-text", None):
    images = Image.open("temp-create.png")
    st.image(images, width=512)

if st.button("Generate New Image"):
    image = query_generate_image_endpoint(text)
    image.save("temp-create.png")
    st.experimental_rerun()

st.markdown("------------")
if st.button("Save Question"):
    # load to s3
    image_id = str(generate_key_for_image_upload())
    object_name = f"generated_images/{image_id}.png"
    load_file_to_s3("temp-create.png", object_name)
    st.success(f"Image generated and uploaded successfully: {object_name}")
    questions_answers = json.dumps(st.session_state["question_answers"], indent=4)

    # insert into DynamoDB
    insert_record_to_dynamodb(image_id, text, object_name, questions_answers)
    st.success(f"An assignment created and saved successfully")

hide_streamlit_style = """
    <style>
        #MainMenu {visibility: hidden;}
        footer{ visibility: hidden;}
    </style>
    """

st.markdown(hide_streamlit_style, unsafe_allow_html=True)
