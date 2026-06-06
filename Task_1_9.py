#!/usr/bin/env python3
"""
EC2 Instance Launcher — კომფორტული CLI ხელსაწყო AWS EC2 ინსტანსის გასაშვებად.
გამოყენება:
    python ec2_launcher.py --vpc-id vpc-xxxxxxxx --subnet-id subnet-xxxxxxxx
    python ec2_launcher.py --vpc-id vpc-xxxxxxxx --subnet-id subnet-xxxxxxxx --custom-ssh-ip 1.2.3.4
"""

import argparse
import sys
import os
import socket
import time
import ipaddress
import urllib.request
import urllib.error

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, EndpointResolutionError


# ── ფერები ტერმინალში ──────────────────────────────────────────────────────────
class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    CYAN   = "\033[96m"
    BLUE   = "\033[94m"

def ok(msg: str)   -> None: print(f"{C.GREEN}  ✔  {C.RESET}{msg}")
def info(msg: str) -> None: print(f"{C.CYAN}  ℹ  {C.RESET}{msg}")
def warn(msg: str) -> None: print(f"{C.YELLOW}  ⚠  {C.RESET}{msg}")
def err(msg: str)  -> None: print(f"{C.RED}  ✖  {C.RESET}{msg}", file=sys.stderr)
def step(msg: str) -> None: print(f"\n{C.BOLD}{C.BLUE}▶ {msg}{C.RESET}")
def banner()       -> None:
    print(f"""
{C.BOLD}{C.CYAN}╔══════════════════════════════════════════════╗
║        AWS EC2 Instance Launcher  v1.0       ║
╚══════════════════════════════════════════════╝{C.RESET}""")


# ── Argument Parser ────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ec2_launcher",
        description="Amazon Linux 3 EC2 ინსტანსის ავტომატური გაშვება.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
მაგალითები:
  %(prog)s --vpc-id vpc-0abc1234 --subnet-id subnet-0abc1234
  %(prog)s --vpc-id vpc-0abc1234 --subnet-id subnet-0abc1234 --custom-ssh-ip 203.0.113.5
  %(prog)s --vpc-id vpc-0abc1234 --subnet-id subnet-0abc1234 --instance-type t3.small --region eu-west-1
        """,
    )

    required = p.add_argument_group("სავალდებულო პარამეტრები")
    required.add_argument("--vpc-id",    required=True, metavar="VPC_ID",    help="AWS VPC-ის ID (vpc-xxxxxxxx)")
    required.add_argument("--subnet-id", required=True, metavar="SUBNET_ID", help="Subnet-ის ID (subnet-xxxxxxxx)")

    optional = p.add_argument_group("არასავალდებულო პარამეტრები")
    optional.add_argument("--custom-ssh-ip",  metavar="IP",    default=None,        help="SSH-ისთვის ნებადართული IP (ავტო-განსაზღვრის ნაცვლად)")
    optional.add_argument("--instance-type",  metavar="TYPE",  default="t3.micro",  help="EC2 ინსტანსის ტიპი (default: t3.micro)")
    optional.add_argument("--key-name",       metavar="NAME",  default="ec2-launcher-key", help="Key Pair-ის სახელი (default: ec2-launcher-key)")
    optional.add_argument("--region",         metavar="REGION",default="us-east-1", help="AWS Region (default: us-east-1)")
    optional.add_argument("--tag-name",       metavar="NAME",  default="ec2-launcher-instance", help="ინსტანსის Name ტეგი")
    optional.add_argument("--ssh-timeout",    metavar="SEC",   type=int, default=180, help="SSH-ის მოლოდინის ლიმიტი წამებში (default: 180)")
    optional.add_argument("--no-wait",        action="store_true", help="SSH კავშირის დადასტურების გარეშე დასრულება")
    return p


# ── IP ვალიდაცია ───────────────────────────────────────────────────────────────
def validate_ip(ip: str) -> str:
    try:
        ipaddress.ip_address(ip)
        return ip
    except ValueError:
        raise argparse.ArgumentTypeError(f"არასწორი IP მისამართი: {ip}")


def get_my_public_ip() -> str:
    """მომხმარებლის გარე IP-ის ავტომატური განსაზღვრა."""
    services = [
        "https://checkip.amazonaws.com",
        "https://api.ipify.org",
        "https://icanhazip.com",
    ]
    for url in services:
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                ip = r.read().decode().strip()
                ipaddress.ip_address(ip)   # ვალიდაცია
                return ip
        except Exception:
            continue
    raise RuntimeError("გარე IP-ის განსაზღვრა ვერ მოხდა. გამოიყენეთ --custom-ssh-ip.")


# ── AWS ვალიდაციები ────────────────────────────────────────────────────────────
def validate_vpc(ec2, vpc_id: str) -> dict:
    step(f"VPC-ის ვალიდაცია: {vpc_id}")
    try:
        resp = ec2.describe_vpcs(VpcIds=[vpc_id])
        vpc  = resp["Vpcs"][0]
        name = next(
            (t["Value"] for t in vpc.get("Tags", []) if t["Key"] == "Name"),
            "—"
        )
        ok(f"VPC ნაპოვნია  |  CIDR: {vpc['CidrBlock']}  |  სახელი: {name}")
        return vpc
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("InvalidVpcID.NotFound", "InvalidVpcID.Malformed"):
            err(f"VPC '{vpc_id}' ვერ მოიძებნა ან ID-ს ფორმატი არასწორია.")
        elif code == "UnauthorizedOperation":
            err("Permission denied — ec2:DescribeVpcs უფლება არ გაქვთ.")
        else:
            err(f"AWS შეცდომა [{code}]: {e.response['Error']['Message']}")
        sys.exit(1)


def validate_subnet(ec2, subnet_id: str, vpc_id: str) -> dict:
    step(f"Subnet-ის ვალიდაცია: {subnet_id}")
    try:
        resp   = ec2.describe_subnets(SubnetIds=[subnet_id])
        subnet = resp["Subnets"][0]
        if subnet["VpcId"] != vpc_id:
            err(f"Subnet '{subnet_id}' ეკუთვნის სხვა VPC-ს ({subnet['VpcId']}), არა {vpc_id}-ს.")
            sys.exit(1)
        ok(
            f"Subnet ნაპოვნია  |  AZ: {subnet['AvailabilityZone']}  "
            f"|  CIDR: {subnet['CidrBlock']}  "
            f"|  თავისუფალი IP-ები: {subnet['AvailableIpAddressCount']}"
        )
        return subnet
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("InvalidSubnetID.NotFound", "InvalidSubnetID.Malformed"):
            err(f"Subnet '{subnet_id}' ვერ მოიძებნა ან ID-ს ფორმატი არასწორია.")
        elif code == "UnauthorizedOperation":
            err("Permission denied — ec2:DescribeSubnets უფლება არ გაქვთ.")
        else:
            err(f"AWS შეცდომა [{code}]: {e.response['Error']['Message']}")
        sys.exit(1)


# ── AMI ძიება ──────────────────────────────────────────────────────────────────
def get_latest_al3_ami(ec2) -> str:
    step("უახლესი Amazon Linux 3 AMI-ის ძიება...")
    try:
        resp = ec2.describe_images(
            Owners=["amazon"],
            Filters=[
                {"Name": "name",                "Values": ["al2023-ami-*-x86_64"]},
                {"Name": "state",               "Values": ["available"]},
                {"Name": "architecture",        "Values": ["x86_64"]},
                {"Name": "virtualization-type", "Values": ["hvm"]},
                {"Name": "root-device-type",    "Values": ["ebs"]},
            ],
        )
        images = resp.get("Images", [])
        if not images:
            err("Amazon Linux 3 (AL2023) AMI ვერ მოიძებნა ამ რეგიონში.")
            sys.exit(1)
        latest = sorted(images, key=lambda x: x["CreationDate"], reverse=True)[0]
        ok(f"AMI ნაპოვნია  |  {latest['ImageId']}  |  {latest['Name']}  |  {latest['CreationDate'][:10]}")
        return latest["ImageId"]
    except ClientError as e:
        err(f"AMI ძიების შეცდომა: {e.response['Error']['Message']}")
        sys.exit(1)


# ── Key Pair ───────────────────────────────────────────────────────────────────
def create_or_reuse_key_pair(ec2, key_name: str) -> str:
    """Key Pair-ის შექმნა და .pem ფაილის შენახვა 0400 უფლებებით."""
    step(f"Key Pair: {key_name}")
    pem_path = f"{key_name}.pem"

    # არსებულის შემოწმება
    try:
        ec2.describe_key_pairs(KeyNames=[key_name])
        if os.path.exists(pem_path):
            ok(f"Key Pair უკვე არსებობს  |  PEM: {pem_path}")
            return pem_path
        else:
            warn(f"Key Pair '{key_name}' AWS-ში არსებობს, მაგრამ {pem_path} ვერ მოიძებნა ლოკალურად.")
            warn("სხვა სახელი მიუთითეთ --key-name-ით ან წაშალეთ არსებული key pair AWS-ში.")
            sys.exit(1)
    except ClientError as e:
        if e.response["Error"]["Code"] != "InvalidKeyPair.NotFound":
            err(f"Key Pair შემოწმების შეცდომა: {e.response['Error']['Message']}")
            sys.exit(1)

    # ახლის შექმნა
    try:
        resp     = ec2.create_key_pair(KeyName=key_name, KeyType="rsa", KeyFormat="pem")
        material = resp["KeyMaterial"]
        with open(pem_path, "w") as f:
            f.write(material)
        os.chmod(pem_path, 0o400)
        ok(f"Key Pair შექმნილია  |  PEM: {os.path.abspath(pem_path)}  |  უფლებები: 0400")
        return pem_path
    except ClientError as e:
        err(f"Key Pair-ის შექმნის შეცდომა: {e.response['Error']['Message']}")
        sys.exit(1)


# ── Security Group ─────────────────────────────────────────────────────────────
def create_security_group(ec2, vpc_id: str, ssh_ip: str, tag_name: str) -> str:
    step("Security Group-ის შექმნა")
    sg_name = f"{tag_name}-sg"
    try:
        resp = ec2.create_security_group(
            GroupName=sg_name,
            Description=f"SSH access for {tag_name}",
            VpcId=vpc_id,
            TagSpecifications=[{
                "ResourceType": "security-group",
                "Tags": [{"Key": "Name", "Value": sg_name},
                         {"Key": "CreatedBy", "Value": "ec2-launcher"}],
            }],
        )
        sg_id = resp["GroupId"]
        ec2.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[{
                "IpProtocol": "tcp",
                "FromPort": 22,
                "ToPort": 22,
                "IpRanges": [{"CidrIp": f"{ssh_ip}/32",
                              "Description": f"SSH from {ssh_ip}"}],
            }],
        )
        ok(f"Security Group შექმნილია  |  {sg_id}  |  SSH: {ssh_ip}/32")
        return sg_id
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "InvalidGroup.Duplicate":
            warn(f"Security Group '{sg_name}' უკვე არსებობს. ვეძებ...")
            try:
                r = ec2.describe_security_groups(
                    Filters=[{"Name": "group-name", "Values": [sg_name]},
                             {"Name": "vpc-id",     "Values": [vpc_id]}]
                )
                sg_id = r["SecurityGroups"][0]["GroupId"]
                ok(f"არსებული Security Group გამოყენება  |  {sg_id}")
                return sg_id
            except (ClientError, IndexError) as inner:
                err(f"Security Group ვერ მოიძებნა: {inner}")
                sys.exit(1)
        elif code == "UnauthorizedOperation":
            err("Permission denied — ec2:CreateSecurityGroup/AuthorizeSecurityGroupIngress.")
        else:
            err(f"Security Group შეცდომა [{code}]: {e.response['Error']['Message']}")
        sys.exit(1)


# ── EC2 Instance შექმნა ────────────────────────────────────────────────────────
def launch_instance(ec2, ami_id: str, instance_type: str, key_name: str,
                    sg_id: str, subnet_id: str, tag_name: str) -> dict:
    step("EC2 ინსტანსის გაშვება")
    try:
        resp = ec2.run_instances(
            ImageId=ami_id,
            InstanceType=instance_type,
            KeyName=key_name,
            MinCount=1,
            MaxCount=1,
            NetworkInterfaces=[{
                "DeviceIndex": 0,
                "SubnetId": subnet_id,
                "Groups": [sg_id],
                "AssociatePublicIpAddress": True,
            }],
            TagSpecifications=[{
                "ResourceType": "instance",
                "Tags": [{"Key": "Name",      "Value": tag_name},
                         {"Key": "CreatedBy", "Value": "ec2-launcher"}],
            }],
        )
        instance = resp["Instances"][0]
        ok(f"ინსტანსი გაშვებულია  |  ID: {instance['InstanceId']}  |  სტატუსი: pending")
        return instance
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "UnauthorizedOperation":
            err("Permission denied — ec2:RunInstances უფლება არ გაქვთ.")
        elif code == "InsufficientInstanceCapacity":
            err(f"ამ AZ-ში '{instance_type}' ტიპის ინსტანსი ხელმიუწვდომელია.")
        elif code == "InvalidParameterValue":
            err(f"პარამეტრის შეცდომა: {e.response['Error']['Message']}")
        else:
            err(f"ინსტანსის გაშვების შეცდომა [{code}]: {e.response['Error']['Message']}")
        sys.exit(1)


# ── მოლოდინი + SSH შემოწმება ───────────────────────────────────────────────────
def wait_for_running(ec2, instance_id: str) -> str:
    step(f"ინსტანსის გააქტიურების მოლოდინი: {instance_id}")
    info("გთხოვთ მოიცადოთ — ეს 1–3 წუთი შეიძლება გაგრძელდეს...")
    try:
        waiter = ec2.get_waiter("instance_running")
        waiter.wait(
            InstanceIds=[instance_id],
            WaiterConfig={"Delay": 10, "MaxAttempts": 30},
        )
    except Exception as e:
        err(f"ინსტანსის გააქტიურების მოლოდინში შეცდომა: {e}")
        sys.exit(1)

    resp      = ec2.describe_instances(InstanceIds=[instance_id])
    inst      = resp["Reservations"][0]["Instances"][0]
    public_ip = inst.get("PublicIpAddress", "")
    ok(f"ინსტანსი გააქტიურდა  |  Public IP: {public_ip}")
    return public_ip


def wait_for_ssh(public_ip: str, timeout: int) -> bool:
    step(f"SSH პორტის (22) ხელმისაწვდომობის შემოწმება: {public_ip}")
    deadline = time.time() + timeout
    attempt  = 0
    while time.time() < deadline:
        attempt += 1
        try:
            with socket.create_connection((public_ip, 22), timeout=5):
                ok(f"SSH პორტი ღიაა! (მცდელობა #{attempt})")
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            remaining = int(deadline - time.time())
            print(f"\r  {C.YELLOW}⟳{C.RESET}  მოლოდინი...  მცდელობა #{attempt}  "
                  f"(დარჩენილია ≈{remaining}წმ)     ", end="", flush=True)
            time.sleep(5)
    print()
    warn(f"SSH {timeout}წმ-ში ვერ გახსნა. ინსტანსი შეიძლება ჯერ კიდევ იტვირთება.")
    return False


# ── შედეგის ბარათი ─────────────────────────────────────────────────────────────
def print_summary(instance_id: str, public_ip: str, pem_path: str,
                  ssh_ok: bool, tag_name: str) -> None:
    ssh_status = f"{C.GREEN}✔ ღია{C.RESET}" if ssh_ok else f"{C.YELLOW}⚠ ჯერ მიუწვდომელი{C.RESET}"
    print(f"""
{C.BOLD}{C.CYAN}╔══════════════════════════════════════════════════════╗
║                   შედეგი / Summary                   ║
╠══════════════════════════════════════════════════════╣{C.RESET}
  ინსტანსი    : {C.BOLD}{instance_id}{C.RESET}
  სახელი      : {tag_name}
  Public IP   : {C.BOLD}{public_ip}{C.RESET}
  PEM ფაილი   : {pem_path}
  SSH სტატუსი : {ssh_status}
{C.BOLD}{C.CYAN}╠══════════════════════════════════════════════════════╣{C.RESET}
  SSH ბრძანება:
  {C.GREEN}ssh -i {pem_path} ec2-user@{public_ip}{C.RESET}
{C.BOLD}{C.CYAN}╚══════════════════════════════════════════════════════╝{C.RESET}
""")


# ── მთავარი ──────────────────────────────────────────────────────────────────
def main() -> None:
    banner()
    parser = build_parser()
    args   = parser.parse_args()

    # boto3 კლიენტი
    try:
        session = boto3.session.Session(region_name=args.region)
        ec2     = session.client("ec2")
        # Credentials-ის სწრაფი შემოწმება
        ec2.describe_availability_zones()
    except NoCredentialsError:
        err("AWS credentials ვერ მოიძებნა. დააყენეთ AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY ან ~/.aws/credentials.")
        sys.exit(1)
    except ClientError as e:
        err(f"AWS კავშირის შეცდომა: {e.response['Error']['Message']}")
        sys.exit(1)
    except Exception as e:
        err(f"AWS კლიენტის ინიციალიზაციის შეცდომა: {e}")
        sys.exit(1)

    info(f"რეგიონი: {args.region}  |  ინსტანსის ტიპი: {args.instance_type}")

    # 1. VPC & Subnet ვალიდაცია
    validate_vpc(ec2, args.vpc_id)
    validate_subnet(ec2, args.subnet_id, args.vpc_id)

    # 2. SSH IP
    step("SSH IP-ის განსაზღვრა")
    if args.custom_ssh_ip:
        validate_ip(args.custom_ssh_ip)
        ssh_ip = args.custom_ssh_ip
        ok(f"გამოყენებული custom IP: {ssh_ip}")
    else:
        try:
            ssh_ip = get_my_public_ip()
            ok(f"ავტომატურად განსაზღვრული IP: {ssh_ip}")
        except RuntimeError as e:
            err(str(e))
            sys.exit(1)

    # 3. AMI
    ami_id = get_latest_al3_ami(ec2)

    # 4. Key Pair
    pem_path = create_or_reuse_key_pair(ec2, args.key_name)

    # 5. Security Group
    sg_id = create_security_group(ec2, args.vpc_id, ssh_ip, args.tag_name)

    # 6. Instance გაშვება
    instance    = launch_instance(ec2, ami_id, args.instance_type,
                                  args.key_name, sg_id, args.subnet_id, args.tag_name)
    instance_id = instance["InstanceId"]

    # 7. გააქტიურების მოლოდინი
    public_ip = wait_for_running(ec2, instance_id)

    # 8. SSH შემოწმება
    ssh_ok = False
    if not args.no_wait and public_ip:
        ssh_ok = wait_for_ssh(public_ip, args.ssh_timeout)
    elif args.no_wait:
        info("--no-wait მითითებულია: SSH შემოწმება გამოტოვებულია.")

    # 9. შედეგი
    print_summary(instance_id, public_ip or "N/A", pem_path, ssh_ok, args.tag_name)


if __name__ == "__main__":
    main()
