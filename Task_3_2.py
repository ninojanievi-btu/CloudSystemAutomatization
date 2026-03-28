import logging
import argparse
from botocore.exceptions import ClientError
from auth import init_client
 
 
def delete_object(s3_client, bucket_name, object_key):
    """
    Delete a specific object from S3 bucket.
    
    Args:
        s3_client: Boto3 S3 client
        bucket_name: Name of the S3 bucket
        object_key: Key (name) of the object to delete
    
    Returns:
        bool: True if deletion successful, False otherwise
    """
    try:
        s3_client.delete_object(
            Bucket=bucket_name,
            Key=object_key
        )
        print(f"Object '{object_key}' successfully deleted from bucket '{bucket_name}'")
        return True
        
    except ClientError as e:
        print(f"Error deleting object: {e}")
        return False
 
 
def main():
    parser = argparse.ArgumentParser(
        description="Delete an object from S3 bucket",
        prog="delete_object.py",
    )
    
    parser.add_argument(
        "-bn",
        "--bucket_name",
        type=str,
        help="S3 bucket name",
        required=True,
    )
    
    parser.add_argument(
        "-k",
        "--key",
        type=str,
        help="Object key (file name) in S3 bucket",
        required=True,
    )
    
    parser.add_argument(
        "-del",
        "--delete",
        help="Delete object from bucket",
        action="store_true",
        required=True,
    )
    
    args = parser.parse_args()
    
    s3_client = init_client()
    
    if args.delete:
        delete_object(s3_client, args.bucket_name, args.key)
 
 
if __name__ == "__main__":
    try:
        main()
    except ClientError as e:
        logging.error(e)