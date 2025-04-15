from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_rds as rds,
    aws_iam as iam,
    CfnOutput,
    RemovalPolicy,
    Duration
)
from constructs import Construct

class TravelAppInfraStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        key_pair_name = "TravelAppKey"
        my_ip_cidr = "108.18.138.68/32"

        # 1. Create VPC with 2 AZs to meet RDS requirement
        vpc = ec2.Vpc(
            self, "TravelAppVPC",
            max_azs=2,
            cidr="10.0.0.0/16",
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="Isolated",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24
                )
            ]
        )

        # Determine target AZ from one of the public subnets
        public_subnets = vpc.select_subnets(subnet_type=ec2.SubnetType.PUBLIC).subnets
        private_subnets = vpc.select_subnets(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS).subnets

        target_az = public_subnets[0].availability_zone
        public_subnet_in_az = next(s for s in public_subnets if s.availability_zone == target_az)
        private_subnet_in_az = next(s for s in private_subnets if s.availability_zone == target_az)

        # 2. Security Groups
        frontend_sg = ec2.SecurityGroup(self, "FrontendSG", vpc=vpc)
        frontend_sg.add_ingress_rule(ec2.Peer.ipv4(my_ip_cidr), ec2.Port.tcp(22), "SSH from my IP")
        frontend_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "HTTP access")
        frontend_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443), "HTTPS access")

        backend_sg = ec2.SecurityGroup(self, "BackendSG", vpc=vpc)
        backend_sg.add_ingress_rule(frontend_sg, ec2.Port.tcp(8080), "API access from frontend")
        backend_sg.add_ingress_rule(ec2.Peer.ipv4(my_ip_cidr), ec2.Port.tcp(22), "SSH from my IP")
        backend_sg.add_ingress_rule(ec2.Peer.ipv4(my_ip_cidr), ec2.Port.tcp(8080), "HTTP 8080 from my IP")

        db_sg = ec2.SecurityGroup(self, "DatabaseSG", vpc=vpc)
        db_sg.add_ingress_rule(backend_sg, ec2.Port.tcp(3306), "MySQL access from backend")

        # 3. RDS
        db = rds.DatabaseInstance(
            self, "TravelDB",
            engine=rds.DatabaseInstanceEngine.mysql(version=rds.MysqlEngineVersion.VER_8_0_33),
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.MICRO),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            security_groups=[db_sg],
            publicly_accessible=False,
            database_name="traveldb",
            credentials=rds.Credentials.from_generated_secret("admin"),
            removal_policy=RemovalPolicy.DESTROY,
            deletion_protection=False,
            backup_retention=Duration.days(7)
        )

        # 4. EC2 Instances (both in the same AZ)
        frontend = ec2.Instance(
            self, "FrontendInstance",
            instance_type=ec2.InstanceType("t2.micro"),
            machine_image=ec2.MachineImage.latest_amazon_linux2(),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnets=[public_subnet_in_az]),
            security_group=frontend_sg,
            key_pair=ec2.KeyPair.from_key_pair_name(self, "KeyPair", key_pair_name=key_pair_name),
            user_data=ec2.UserData.custom("""#!/bin/bash
                sudo yum update -y
                sudo yum install -y git
                sudo curl -fsSL https://rpm.nodesource.com/setup_22.x | bash -
                yum install -y nodejs
                amazon-linux-extras install docker -y
                service docker start
                usermod -aG docker ec2-user
                git clone https://github.com/your-repo.git /home/ec2-user/app
                cd /home/ec2-user/app
                npm install
                npm run build
                npm start
            """)
        )

        backend = ec2.Instance(
            self, "BackendInstance",
            instance_type=ec2.InstanceType("t2.micro"),
            machine_image=ec2.MachineImage.latest_amazon_linux2(),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnets=[private_subnet_in_az]),
            security_group=backend_sg,
            key_pair=ec2.KeyPair.from_key_pair_name(self, "KeyPairBackend", key_pair_name=key_pair_name),
            user_data=ec2.UserData.custom(f"""#!/bin/bash
                sudo yum update -y
                sudo yum install -y java-17-amazon-corretto
                sudo dnf install docker -y
                sudo service docker start
                newgrp docker
                sudo usermod -aG docker ec2-user
                sudo yum install https://dev.mysql.com/get/mysql80-community-release-el7-7.noarch.rpm -y
                
                echo \"spring.datasource.url=jdbc:mysql://{db.db_instance_endpoint_address}/traveldb\" > /home/ec2-user/application.properties
                echo \"spring.datasource.username=admin\" >> /home/ec2-user/application.properties
                echo \"spring.datasource.password=$(aws secretsmanager get-secret-value --secret-id {db.secret.secret_arn} --query SecretString --output text | jq -r .password)\" >> /home/ec2-user/application.properties
                java -jar /home/ec2-user/app.jar --spring.config.location=file:/home/ec2-user/application.properties
            """)
        )

        backend.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("SecretsManagerReadWrite")
        )

        # 5. Outputs
        CfnOutput(self, "FrontendURL", value=f"http://{frontend.instance_public_ip}")
        CfnOutput(self, "BackendPrivateIP", value=backend.instance_private_ip)
        CfnOutput(self, "DatabaseEndpoint", value=db.db_instance_endpoint_address)
        CfnOutput(self, "SSHCommand", value=f"ssh -i {key_pair_name}.pem ec2-user@{frontend.instance_public_ip}")
