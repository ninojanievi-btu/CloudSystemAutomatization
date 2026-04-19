import argparse
import boto3
import os
import mimetypes

s3 = boto3.client('s3')


def create_bucket(bucket_name, region='eu-central-1'):
    if region == 'us-east-1':
        s3.create_bucket(Bucket=bucket_name)
    else:
        s3.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={'LocationConstraint': region}
        )


def upload_directory(bucket_name, directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            local_path = os.path.join(root, file)
            relative_path = os.path.relpath(local_path, directory)
            s3_path = relative_path.replace("\\", "/")

            content_type, _ = mimetypes.guess_type(local_path)

            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type

            print(f"Uploading {s3_path}...")
            s3.upload_file(local_path, bucket_name, s3_path, ExtraArgs=extra_args)


def configure_website(bucket_name):
    s3.put_bucket_website(
        Bucket=bucket_name,
        WebsiteConfiguration={
            'IndexDocument': {'Suffix': 'index.html'},
            'ErrorDocument': {'Key': 'index.html'}
        }
    )


def set_public_policy(bucket_name):
    policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": ["s3:GetObject"],
            "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
        }]
    }

    import json
    s3.put_bucket_policy(
        Bucket=bucket_name,
        Policy=json.dumps(policy)
    )


def get_website_url(bucket_name, region='eu-central-1'):
    return f"http://{bucket_name}.s3-website-{region}.amazonaws.com"


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')

    host_parser = subparsers.add_parser('host')
    host_parser.add_argument('bucket_name')
    host_parser.add_argument('--source', required=True)
    host_parser.add_argument('--region', default='eu-central-1')

    args = parser.parse_args()

    if args.command == 'host':
        bucket = args.bucket_name
        source = args.source
        region = args.region

        print("Creating bucket...")
        create_bucket(bucket, region)

        print("Uploading files...")
        upload_directory(bucket, source)

        print("Configuring website...")
        configure_website(bucket)

        print("Setting public access...")
        set_public_policy(bucket)

        url = get_website_url(bucket, region)
        print(f"\n✅ Website उपलब्धია აქ: {url}")


if __name__ == "__main__":
    main()