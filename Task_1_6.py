import boto3
import argparse
import mimetypes
import os
import sys
import json
from os import getenv

s3_client = boto3.client(
    "s3",
    aws_access_key_id=getenv("aws_access_key_id"),
    aws_secret_access_key=getenv("aws_secret_access_key"),
    aws_session_token=getenv("aws_session_token"),
    region_name=getenv("aws_region_name", "us-east-1"),
)

REGION = getenv("aws_region_name", "us-east-1")


# ──────────────────────────────────────────────
# Step 1: Create bucket (if it doesn't exist)
# ──────────────────────────────────────────────
def create_bucket(bucket_name):
    print(f"\n[1/4] Creating bucket '{bucket_name}'...")
    try:
        if REGION == "us-east-1":
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )
        print(f"      Bucket created.")
    except s3_client.exceptions.BucketAlreadyOwnedByYou:
        print(f"      Bucket already exists and is owned by you — reusing it.")
    except Exception as e:
        print(f"      ERROR creating bucket: {e}")
        sys.exit(1)


# ──────────────────────────────────────────────
# Step 2: Upload all files from source folder
# ──────────────────────────────────────────────
def upload_files(bucket_name, source_folder):
    print(f"\n[2/4] Uploading files from '{source_folder}' to bucket...")

    if not os.path.isdir(source_folder):
        print(f"      ERROR: Source folder '{source_folder}' does not exist.")
        sys.exit(1)

    uploaded = 0
    for root, dirs, files in os.walk(source_folder):
        # Skip hidden dirs like .git
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for filename in files:
            if filename.startswith("."):
                continue
            local_path = os.path.join(root, filename)
            # S3 key = relative path from source folder, using forward slashes
            s3_key = os.path.relpath(local_path, source_folder).replace("\\", "/")

            content_type, _ = mimetypes.guess_type(local_path)
            if content_type is None:
                content_type = "application/octet-stream"

            s3_client.upload_file(
                local_path,
                bucket_name,
                s3_key,
                ExtraArgs={"ContentType": content_type},
            )
            print(f"      Uploaded: {s3_key} ({content_type})")
            uploaded += 1

    print(f"      Total files uploaded: {uploaded}")


# ──────────────────────────────────────────────
# Step 3: Configure static website hosting
# ──────────────────────────────────────────────
def configure_website(bucket_name, index_doc, error_doc):
    print(f"\n[3/4] Configuring WebsiteConfiguration...")
    s3_client.put_bucket_website(
        Bucket=bucket_name,
        WebsiteConfiguration={
            "IndexDocument": {"Suffix": index_doc},
            "ErrorDocument": {"Key": error_doc},
        },
    )
    print(f"      Index document : {index_doc}")
    print(f"      Error document : {error_doc}")


# ──────────────────────────────────────────────
# Step 4: Make bucket publicly readable
# ──────────────────────────────────────────────
def set_public_access(bucket_name):
    print(f"\n[4/4] Setting public access permissions...")

    # Disable the "block all public access" settings
    s3_client.put_public_access_block(
        Bucket=bucket_name,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": False,
            "IgnorePublicAcls": False,
            "BlockPublicPolicy": False,
            "RestrictPublicBuckets": False,
        },
    )

    # Attach a bucket policy that allows public GetObject
    public_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "PublicReadGetObject",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{bucket_name}/*",
            }
        ],
    }
    s3_client.put_bucket_policy(
        Bucket=bucket_name,
        Policy=json.dumps(public_policy),
    )
    print(f"      Public read policy applied.")


# ──────────────────────────────────────────────
# Build the website URL
# ──────────────────────────────────────────────
def get_website_url(bucket_name):
    # URL format differs slightly by region
    if REGION == "us-east-1":
        return f"http://{bucket_name}.s3-website-us-east-1.amazonaws.com"
    else:
        return f"http://{bucket_name}.s3-website.{REGION}.amazonaws.com"


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────
def cmd_host(args):
    bucket_name = args.bucket
    source = args.source
    index_doc = args.index
    error_doc = args.error

    create_bucket(bucket_name)
    upload_files(bucket_name, source)
    configure_website(bucket_name, index_doc, error_doc)
    set_public_access(bucket_name)

    url = get_website_url(bucket_name)
    print(f"\n{'='*55}")
    print(f"  Static website is live!")
    print(f"  URL: {url}")
    print(f"{'='*55}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Host a static website on AWS S3 with one command."
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    # "host" subcommand
    host_parser = subparsers.add_parser(
        "host",
        help="Create a bucket, upload site files, and enable static website hosting."
    )
    host_parser.add_argument(
        "bucket",
        help="S3 bucket name (must be globally unique, e.g. my-s3-static-host)"
    )
    host_parser.add_argument(
        "--source",
        required=True,
        metavar="FOLDER",
        help="Path to the local folder containing your website files"
    )
    host_parser.add_argument(
        "--index",
        default="index.html",
        metavar="FILE",
        help="Index document filename (default: index.html)"
    )
    host_parser.add_argument(
        "--error",
        default="404.html",
        metavar="FILE",
        help="Error document filename (default: 404.html)"
    )
    host_parser.set_defaults(func=cmd_host)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
