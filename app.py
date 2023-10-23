#!/usr/bin/env python3
import os
import json

import aws_cdk as cdk

from cdk.cdk_stack import CdkStack

app = cdk.App()

instance = app.node.try_get_context("environment")
if not instance: 
    raise ValueError("Missing environment in the application context.")

with open("parameters.json", "r") as param_file:
    param_data = param_file.read()

config_all = json.loads(param_data)
config = config_all["Parameters"][instance]

cdkStack = CdkStack(app, "AiLearningPortalDemo", config=config)

app.synth()
