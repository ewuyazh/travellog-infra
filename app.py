#!/usr/bin/env python3

import aws_cdk as cdk
from infra_stack import TravelAppInfraStack

app = cdk.App()

TravelAppInfraStack(app, "TravelAppInfraStack")

app.synth()
