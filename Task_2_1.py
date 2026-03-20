import argparse
import boto3
from botocore.exceptions import ClientError
 
def check_and_create_bucket(bucket_name):
    s3_client = boto3.client('s3')
    
    try:
        # Check if bucket exists
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"Bucket '{bucket_name}' already exists!")
        return True
    except ClientError as e:
        # If 404, bucket doesn't exist
        if e.response['Error']['Code'] == '404':
            try:
                # Create bucket
                s3_client.create_bucket(Bucket=bucket_name)
                print(f"Bucket '{bucket_name}' created successfully!")
                return True
            except ClientError as err:
                print(f"Error creating bucket: {err}")
                return False
        else:
            print(f"Error: {e}")
            return False
 
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='S3 Bucket Manager')
    parser.add_argument('bucket_name', type=str, help='Name of S3 bucket')
    
    args = parser.parse_args()
    check_and_create_bucket(args.bucket_name)