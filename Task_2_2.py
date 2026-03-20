import argparse
import boto3
import json
from botocore.exceptions import ClientError
 
def check_and_set_policy(bucket_name):
    s3_client = boto3.client('s3')
    
    try:
        s3_client.get_bucket_policy(Bucket=bucket_name)
        print(f"Bucket '{bucket_name}' already has a policy!")
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchBucketPolicy':
            policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": [
                        f"arn:aws:s3:::{bucket_name}/dev/*",
                        f"arn:aws:s3:::{bucket_name}/test/*"
                    ]
                }]
            }
            
            s3_client.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))
            print(f"Policy created for '{bucket_name}'!")
        else:
            print(f"Error: {e}")
 
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='S3 Bucket Policy Manager')
    parser.add_argument('bucket_name', type=str, help='S3 bucket name')
    args = parser.parse_args()
    check_and_set_policy(args.bucket_name)