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

        key_name = "TravelAppKey"  # Define your EC2 key pair name here

        # 1. Create VPC with public/private subnets
        vpc = ec2.Vpc(
            self, "TravelAppVPC",
            max_azs=2,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="Public", subnet_type=ec2.SubnetType.PUBLIC),
                ec2.SubnetConfiguration(name="Private", subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
            ]
        )

        # 2. Security Groups
        frontend_sg = ec2.SecurityGroup(self, "FrontendSG", vpc=vpc)
        frontend_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(22), "SSH from anywhere")
        frontend_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "HTTP access")
        frontend_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443), "HTTPS access")

        backend_sg = ec2.SecurityGroup(self, "BackendSG", vpc=vpc)
        backend_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(22), "SSH from anywhere")
        backend_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(8080), "Public API access (testing)")
        backend_sg.add_ingress_rule(frontend_sg, ec2.Port.tcp(8080), "Allow API access from frontend")

        # 3. EC2 Instances
        frontend = ec2.Instance(
            self, "FrontendInstance",
            instance_type=ec2.InstanceType("t2.micro"),
            machine_image=ec2.MachineImage.latest_amazon_linux(),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=frontend_sg,
            key_name=key_name,
            user_data=ec2.UserData.custom("""#!/bin/bash
                yum update -y
                yum install -y git
                curl -fsSL https://rpm.nodesource.com/setup_22.x | bash -
                yum install -y nodejs
                amazon-linux-extras install docker -y
                sudo service docker start
                usermod -aG docker ec2-user
                amazon-linux-extras enable nginx1
                yum clean metadata
                yum install -y nginx
                systemctl start nginx
                systemctl enable nginx
                cat > /etc/nginx/conf.d/frontend.conf << EOF
                server {
                    listen 80;
                    server_name _;
                    location / {
                        proxy_pass http://localhost:3000;
                        proxy_http_version 1.1;
                        proxy_set_header Upgrade $http_upgrade;
                        proxy_set_header Connection 'upgrade';
                        proxy_set_header Host $host;
                        proxy_cache_bypass $http_upgrade;
                    }
                }
                EOF
                systemctl restart nginx
                # git clone <your-repo-url> /home/ec2-user/app
                # cd /home/ec2-user/app
                # npm install
                # npm run build
                # npm start
            """)
        )

        backend = ec2.Instance(
            self, "BackendInstance",
            instance_type=ec2.InstanceType("t2.micro"),
            machine_image=ec2.MachineImage.latest_amazon_linux(),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=backend_sg,
            key_name=key_name,
            user_data=ec2.UserData.custom("""#!/bin/bash
                yum update -y
                yum install -y java-17-amazon-corretto
                yum install -y mysql
                amazon-linux-extras install docker -y
                sudo service docker start
                usermod -aG docker ec2-user
                docker run hello-world
            """)
        )

        # 5. Outputs
        CfnOutput(self, "FrontendURL", value=f"http://{frontend.instance_public_ip}")
        CfnOutput(self, "BackendPrivateIP", value=backend.instance_private_ip)
        CfnOutput(self, "SSHCommand", value=f"ssh -i {key_name}.pem ec2-user@{frontend.instance_public_ip}")
