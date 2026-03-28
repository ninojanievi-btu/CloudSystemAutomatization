import argparse
import os
from botocore.exceptions import ClientError
from auth import init_client
 
 
def organize_by_extension(s3_client, bucket_name):
    """Organize objects in bucket by extension into folders."""
    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        
        if 'Contents' not in response:
            print("Bucket is empty")
            return
        
        extension_count = {}
        
        for obj in response['Contents']:
            key = obj['Key']
            
            # Skip if it's a folder
            if key.endswith('/'):
                continue
            
            # Get file extension
            if '.' in key:
                ext = key.split('.')[-1].lower()
            else:
                ext = 'no_extension'
            
            # Create folder path with extension
            folder_path = f"{ext}/"
            new_key = f"{folder_path}{key}"
            
            # Skip if already in extension folder
            if key.startswith(f"{ext}/"):
                continue
            
            # Copy object to new location
            copy_source = {'Bucket': bucket_name, 'Key': key}
            s3_client.copy_object(
                CopySource=copy_source,
                Bucket=bucket_name,
                Key=new_key
            )
            
            # Delete original object
            s3_client.delete_object(Bucket=bucket_name, Key=key)
            
            # Count operations by extension
            extension_count[ext] = extension_count.get(ext, 0) + 1
        
        # Print results
        print("\nOrganization complete:\n")
        for ext, count in sorted(extension_count.items()):
            print(f"{ext} - {count}")
    
    except ClientError as e:
        print(f"Error: {e}")
 
 
def main():
    parser = argparse.ArgumentParser(description="Organize S3 bucket by file extension")
    parser.add_argument("-bn", "--bucket_name", type=str, required=True, help="Bucket name")
    parser.add_argument("-org", "--organize", action="store_true", help="Organize bucket by extension")
    
    args = parser.parse_args()
    s3_client = init_client()
    
    if args.organize:
        organize_by_extension(s3_client, args.bucket_name)
 
 
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")