from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_rds as rds,
)
from constructs import Construct

class TravelAppInfraStack(Stack):

    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # VPC
        vpc = ec2.Vpc(self, "TravelAppVPC", max_azs=2)

        # Security group for EC2
        ec2_sg = ec2.SecurityGroup(
            self, "EC2SecurityGroup",
            vpc=vpc,
            description="Allow SSH, HTTP (8080), HTTPS",
            allow_all_outbound=True
        )
        ec2_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(22), "SSH")
        ec2_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(8080), "Spring Boot HTTP")
        ec2_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443), "HTTPS")

        # EC2 instance
        ec2_instance = ec2.Instance(
            self, "TravelAppInstance",
            instance_type=ec2.InstanceType("t2.micro"),
            machine_image=ec2.MachineImage.latest_amazon_linux2(),
            vpc=vpc,
            security_group=ec2_sg,
            key_name="your-key-pair-name"  # replace with actual name
        )

        # Security group for RDS
        rds_sg = ec2.SecurityGroup(
            self, "RDSSecurityGroup",
            vpc=vpc,
            description="Allow MySQL access from EC2",
            allow_all_outbound=True
        )
        rds_sg.add_ingress_rule(ec2_sg, ec2.Port.tcp(3306), "MySQL from EC2")

        # RDS instance
        db = rds.DatabaseInstance(
            self, "TravelAppRDS",
            engine=rds.DatabaseInstanceEngine.mysql(
                version=rds.MysqlEngineVersion.VER_8_0_34
            ),
            instance_type=ec2.InstanceType("t3.micro"),
            vpc=vpc,
            vpc_subnets={"subnet_type": ec2.SubnetType.PUBLIC},
            multi_az=False,
            allocated_storage=20,
            storage_encrypted=True,
            database_name="traveldb",
            credentials=rds.Credentials.from_generated_secret("admin"),
            security_groups=[rds_sg],
            publicly_accessible=True
        )
