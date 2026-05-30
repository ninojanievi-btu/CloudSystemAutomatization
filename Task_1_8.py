import boto3
import argparse
import ipaddress
from os import getenv
from pprint import pprint

ec2_client = boto3.client(
    "ec2",
    aws_access_key_id=getenv("aws_access_key_id"),
    aws_secret_access_key=getenv("aws_secret_access_key"),
    aws_session_token=getenv("aws_session_token"),
    region_name=getenv("aws_region_name", "us-east-1"),
)


def create_vpc(cidr_block, vpc_name):
    print(f"\n[+] Creating VPC with CIDR {cidr_block}...")
    result = ec2_client.create_vpc(CidrBlock=cidr_block)
    vpc = result.get("Vpc")
    vpc_id = vpc.get("VpcId")
    ec2_client.create_tags(
        Resources=[vpc_id],
        Tags=[{"Key": "Name", "Value": vpc_name}]
    )
    print(f"    VPC created: {vpc_id} (name: {vpc_name})")
    return vpc_id


def create_or_get_igw(vpc_id):
    igw_response = ec2_client.describe_internet_gateways(
        Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}]
    )
    if igw_response["InternetGateways"]:
        igw_id = igw_response["InternetGateways"][0]["InternetGatewayId"]
        print(f"    Using existing IGW: {igw_id}")
    else:
        response = ec2_client.create_internet_gateway()
        igw_id = response["InternetGateway"]["InternetGatewayId"]
        ec2_client.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
        print(f"    Created and attached IGW: {igw_id}")
    return igw_id


def create_subnet(vpc_id, cidr_block, subnet_name):
    response = ec2_client.create_subnet(VpcId=vpc_id, CidrBlock=cidr_block)
    subnet = response["Subnet"]
    subnet_id = subnet["SubnetId"]
    ec2_client.create_tags(
        Resources=[subnet_id],
        Tags=[{"Key": "Name", "Value": subnet_name}]
    )
    print(f"    Subnet created: {subnet_id} | CIDR: {cidr_block} | Name: {subnet_name}")
    return subnet_id


def create_route_table(vpc_id, name, igw_id=None):
    response = ec2_client.create_route_table(VpcId=vpc_id)
    rt_id = response["RouteTable"]["RouteTableId"]
    ec2_client.create_tags(
        Resources=[rt_id],
        Tags=[{"Key": "Name", "Value": name}]
    )
    if igw_id:
        ec2_client.create_route(
            DestinationCidrBlock="0.0.0.0/0",
            GatewayId=igw_id,
            RouteTableId=rt_id,
        )
        print(f"    Route table (public) created: {rt_id} with 0.0.0.0/0 -> {igw_id}")
    else:
        print(f"    Route table (private) created: {rt_id} (no internet route)")
    return rt_id


def associate_route_table(route_table_id, subnet_id):
    ec2_client.associate_route_table(RouteTableId=route_table_id, SubnetId=subnet_id)


def enable_auto_public_ips(subnet_id):
    ec2_client.modify_subnet_attribute(
        MapPublicIpOnLaunch={"Value": True},
        SubnetId=subnet_id
    )


def generate_subnets(base_cidr, n_public, n_private):
    """
    Splits the VPC CIDR into enough /24 subnets for public + private.
    e.g. VPC 10.0.0.0/16 -> 10.0.0.0/24, 10.0.1.0/24, ...
    """
    network = ipaddress.IPv4Network(base_cidr, strict=False)
    subnets = list(network.subnets(new_prefix=24))
    total_needed = n_public + n_private
    if len(subnets) < total_needed:
        raise ValueError(
            f"VPC CIDR {base_cidr} can only fit {len(subnets)} /24 subnets, "
            f"but {total_needed} were requested."
        )
    public_cidrs = [str(subnets[i]) for i in range(n_public)]
    private_cidrs = [str(subnets[i + n_public]) for i in range(n_private)]
    return public_cidrs, private_cidrs


def main():
    parser = argparse.ArgumentParser(
        description="Create an AWS VPC with public and private subnets."
    )
    parser.add_argument(
        "--vpc-name",
        default="btuVPC",
        help="Name tag for the VPC (default: btuVPC)"
    )
    parser.add_argument(
        "--vpc-cidr",
        default="10.0.0.0/16",
        help="CIDR block for the VPC (default: 10.0.0.0/16)"
    )
    parser.add_argument(
        "--public-subnets",
        type=int,
        default=1,
        metavar="N",
        help="Number of public subnets to create (default: 1, max: 200)"
    )
    parser.add_argument(
        "--private-subnets",
        type=int,
        default=1,
        metavar="N",
        help="Number of private subnets to create (default: 1, max: 200)"
    )

    args = parser.parse_args()

    # Validate subnet counts
    for label, count in [("public", args.public_subnets), ("private", args.private_subnets)]:
        if count < 1:
            parser.error(f"--{label}-subnets must be at least 1.")
        if count > 200:
            parser.error(
                f"--{label}-subnets cannot exceed 200. AWS default limit is 200 subnets "
                f"per VPC. Contact AWS Support to request a limit increase."
            )

    print(f"\n{'='*55}")
    print(f"  VPC Name      : {args.vpc_name}")
    print(f"  VPC CIDR      : {args.vpc_cidr}")
    print(f"  Public subnets: {args.public_subnets}")
    print(f"  Private subnets: {args.private_subnets}")
    print(f"{'='*55}")

    # Generate CIDR blocks
    try:
        public_cidrs, private_cidrs = generate_subnets(
            args.vpc_cidr, args.public_subnets, args.private_subnets
        )
    except ValueError as e:
        parser.error(str(e))

    # Create VPC
    vpc_id = create_vpc(args.vpc_cidr, args.vpc_name)

    # Create IGW (needed for public subnets)
    print("\n[+] Setting up Internet Gateway...")
    igw_id = create_or_get_igw(vpc_id)

    # Create shared route tables (one public, one private)
    print("\n[+] Creating route tables...")
    public_rt_id = create_route_table(vpc_id, f"{args.vpc_name}-public-rt", igw_id=igw_id)
    private_rt_id = create_route_table(vpc_id, f"{args.vpc_name}-private-rt", igw_id=None)

    # Create public subnets
    print(f"\n[+] Creating {args.public_subnets} public subnet(s)...")
    for i, cidr in enumerate(public_cidrs, start=1):
        subnet_id = create_subnet(vpc_id, cidr, f"{args.vpc_name}-public-{i}")
        associate_route_table(public_rt_id, subnet_id)
        enable_auto_public_ips(subnet_id)  # public subnets auto-assign public IPs

    # Create private subnets
    print(f"\n[+] Creating {args.private_subnets} private subnet(s)...")
    for i, cidr in enumerate(private_cidrs, start=1):
        subnet_id = create_subnet(vpc_id, cidr, f"{args.vpc_name}-private-{i}")
        associate_route_table(private_rt_id, subnet_id)
        # private subnets do NOT get auto-assign public IPs (default is False)

    print(f"\n{'='*55}")
    print(f"  Done! VPC {vpc_id} fully configured.")
    print(f"  Public subnets : {args.public_subnets} (auto-public-IP enabled, route to IGW)")
    print(f"  Private subnets: {args.private_subnets} (no public IP, no internet route)")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
