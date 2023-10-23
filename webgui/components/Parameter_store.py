import os

import streamlit as st

# access system parameter using boto3
# ssm = boto3.client('ssm')
# get the value of the parameter
#  = ssm.get_parameter(Name='/ai_education_demo/s3_bucket_name', WithDecryption=False)
# S3_BUCKET_NAME = parameter['Parameter']['Value']
# parameter = ssm.get_parameter(Name='/ai_education_demo/ai21_api_key', WithDecryption=False)
# AI21_API_KEY = parameter['Parameter']['Value']
S3_BUCKET_NAME = os.environ.get('s3_bucket_name')
AI21_API_KEY = os.environ.get('ai21_api_key')


