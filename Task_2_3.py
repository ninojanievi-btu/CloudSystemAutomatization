import argparse
import boto3
from botocore.exceptions import ClientError
 
def delete_bucket(bucket_name):
    s3_client = boto3.client('s3')
    
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        s3_client.delete_bucket(Bucket=bucket_name)
        print(f"Bucket '{bucket_name}' deleted successfully!")
        
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            print(f"Bucket '{bucket_name}' does not exist!")
        else:
            print(f"Error: {e}")
 
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='S3 Bucket Delete')
    parser.add_argument('bucket_name', type=str, help='S3 bucket name')
    args = parser.parse_args()
    delete_bucket(args.bucket_name)