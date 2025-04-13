from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    CfnOutput,
    aws_elasticloadbalancingv2 as elbv2,
)
from constructs import Construct
import requests

class TravelAppInfraStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # 1. Get your public IP for SSH access
        try:
            my_ip = requests.get('https://checkip.amazonaws.com').text.strip()
            my_ip_cidr = f"{my_ip}/32"
        except:
            my_ip_cidr = "123.45.67.89/32"  # ← REPLACE WITH YOUR ACTUAL IP

        # 2. Create VPC with public/private subnets
        vpc = ec2.Vpc(
            self, "TravelAppVPC",
            max_azs=2,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="Public", subnet_type=ec2.SubnetType.PUBLIC),
                ec2.SubnetConfiguration(name="Private", subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
            ]
        )

        # 3. Security Groups
        # Frontend (React)
        frontend_sg = ec2.SecurityGroup(self, "FrontendSG", vpc=vpc)
        frontend_sg.add_ingress_rule(ec2.Peer.ipv4(my_ip_cidr), ec2.Port.tcp(22), "SSH from my IP")
        frontend_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "HTTP access")
        frontend_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443), "HTTPS access")

        # Backend (Spring Boot)
        backend_sg = ec2.SecurityGroup(self, "BackendSG", vpc=vpc)
        backend_sg.add_ingress_rule(frontend_sg, ec2.Port.tcp(8080), "Allow API access from frontend")

        # 4. EC2 Instances
        # Frontend (React Docker)
        frontend = ec2.Instance(
            self, "FrontendInstance",
            instance_type=ec2.InstanceType("t2.micro"),
            machine_image=ec2.MachineImage.latest_amazon_linux(),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=frontend_sg,
            key_name="TravelAppKey",  # ← REPLACE
            user_data=ec2.UserData.custom(f"""#!/bin/bash
                # Install Docker
                yum update -y
                yum install -y docker
                systemctl start docker
                usermod -aG docker ec2-user

                # Run React app
                docker run -d -p 80:80 -e REACT_APP_API_URL=http://$BACKEND_PRIVATE_IP:8080 react-app
            """)
        )

        # Backend (Spring Boot)
        backend = ec2.Instance(
            self, "BackendInstance",
            instance_type=ec2.InstanceType("t2.micro"),
            machine_image=ec2.MachineImage.latest_amazon_linux(),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_group=backend_sg,
            key_name="TravelAppKey",  # ← REPLACE
            user_data=ec2.UserData.custom("""#!/bin/bash
                # Install Java
                yum install -y java-17-amazon-corretto

                # Run Spring Boot (configure your DB connection manually)
                nohup java -jar app.jar --server.port=8080 &
            """)
        )

        # 5. Outputs
        CfnOutput(self, "FrontendURL", value=f"http://{frontend.instance_public_ip}")
        CfnOutput(self, "BackendPrivateIP", value=backend.instance_private_ip)
        CfnOutput(self, "SSHCommand",
            value=f"ssh -i TravelAppKey.pem ec2-user@{frontend.instance_public_ip}")