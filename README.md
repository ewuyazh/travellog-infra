# TravelApp Infrastructure (CDK)

This CDK project sets up the infrastructure for the **TravelApp** backend using AWS services:

- An EC2 instance (for deploying the Spring Boot backend in Docker)
- A MySQL database on Amazon RDS
- Security groups for access control
- A custom VPC (with public subnets)

## 🛠 Stack Overview

| Resource         | Description                                                    |
|------------------|----------------------------------------------------------------|
| VPC              | Custom VPC across 2 AZs with public subnets                    |
| EC2 Instance     | Amazon Linux 2, t2.micro, Docker installed                     |
| RDS MySQL        | MySQL 8.0 instance, publicly accessible (for demo only)        |
| Security Groups  | EC2 allows SSH/HTTP/HTTPS, RDS only accepts EC2 access         |

## 📦 Prerequisites

- AWS CLI configured
- AWS CDK v2 installed
- Python 3.7+
- Docker (for building and running the backend)
- A key pair created in your AWS region (for EC2 SSH access)

## 📁 Project Structure
travelapp-infra/
│
├── cdk.json
├── app.py
└── travelapp_infra/
└── travelapp_infra_stack.py

## 🚀  Build the Infrastructure with AWS CDK (Python)

### Step 1: Set Up Your Environment


```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install CDK dependencies
pip install -r requirements.txt

# Bootstrap (if first time)
cdk bootstrap

# Deploy the stack
cdk deploy

🔑 EC2 Access

Make sure to update the stack with your EC2 key pair name:
```python
key_name="your-key-name"
```

Then SSH into the EC2 instance after deployment:

chmod 400 your-key.pem
ssh -i your-key.pem ec2-user@<ec2-public-dns>

🧪 Verify RDS Connection

From the EC2 instance:
mysql -h <rds-endpoint> -u admin -p

🔐 Security Notes
	•	RDS is publicly accessible in this demo. For production, consider:
	•	Putting EC2 and RDS in private subnets
	•	Using Secrets Manager for DB credentials
	•	Using an Application Load Balancer (ALB) for HTTPS termination

🧹 Cleanup

To avoid ongoing charges:
```bash
cdk destroy
```


## AWS Infrastructure Manual Setup (One-Time Only)

### 1: Set Up an EC2 Instance
- Launch an EC2 instance:
- Go to AWS EC2 console
- Click "Launch Instance"
- Choose an Amazon Linux 2 AMI (or Ubuntu if you prefer)
- Select t2.micro (free tier eligible)
- Configure security group to allow:
    * SSH (port 22)
    * HTTP (port 8080) // this is the default port for spring boot
    * HTTPS (port 443)

### 2: Launch the instance and download the key pair

### 3: Connect to your instance via SSH:
```bash
chmod 400 your-key-pair.pem
ssh -i your-key-pair.pem ec2-user@your-instance-public-dns
```

### 4: Update and install Docker + Docker Compose (v2)
```bash
sudo yum update -y
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker
sudo groupadd docker
sudo usermod -aG docker ec2-user  # So you can run docker without sudo

sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
docker-compose version
```

### 5: Install Required Software
```bash
sudo yum update -y
sudo yum install java-23-amazon-corretto-devel -y  # Install Java (for Spring Boot) for Amazon Linux
sudo dnf install mariadb105 # Database Client 
```
### 6:: Create RDS for MySql database
Please note:

- ✅ RDS instance endpoint, port, DB name, username, and password.
- ✅ The same VPC or at least network connectivity between EC2 and RDS.
- ✅ RDS should be password-authenticated (which it is by default unless you’re using IAM or SSL-only).

### 7: Configure Security Group
Make sure your RDS security group allows inbound traffic from your EC2 instance:
- Go to RDS > Databases > [Your DB] > Connectivity & security.
- Find the security group and click on it.
- Under Inbound rules, add:
- Type: e.g., MySQL/Aurora
- Port: 3306 (MySQL)
- Source: The EC2 security group, or EC2’s private IP range (e.g., 10.0.0.0/16)

**There is an option to create the EC2 connection when creating RDS.**

### 8. Verify EC2-RDS communication
From EC2 ssh terminal:
```bash
mysql -h your-db-endpoint.rds.amazonaws.com -P 3306 -u yourUsername -p
```
