import argparse
from botocore.exceptions import ClientError
from auth import init_client
 
 
def check_versioning(s3_client, bucket_name):
    """Check if versioning is enabled for bucket."""
    try:
        response = s3_client.get_bucket_versioning(Bucket=bucket_name)
        status = response.get('Status', 'Not set')
        print(f"Versioning status: {status}")
    except ClientError as e:
        print(f"Error: {e}")
 
 
def list_versions(s3_client, bucket_name, object_key):
    """List all versions of an object with creation dates."""
    try:
        response = s3_client.list_object_versions(
            Bucket=bucket_name,
            Prefix=object_key
        )
        
        versions = [v for v in response.get('Versions', []) if v['Key'] == object_key]
        
        if not versions:
            print(f"No versions found for '{object_key}'")
            return
        
        print(f"\nTotal versions: {len(versions)}\n")
        for idx, v in enumerate(versions, 1):
            latest = " [LATEST]" if v.get('IsLatest') else ""
            print(f"{idx}. Version ID: {v['VersionId']}{latest}")
            print(f"   Date: {v['LastModified'].strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    except ClientError as e:
        print(f"Error: {e}")
 
 
def restore_version(s3_client, bucket_name, object_key):
    """Restore previous version as latest."""
    try:
        response = s3_client.list_object_versions(
            Bucket=bucket_name,
            Prefix=object_key
        )
        
        versions = sorted(
            [v for v in response.get('Versions', []) if v['Key'] == object_key],
            key=lambda x: x['LastModified'],
            reverse=True
        )
        
        if len(versions) < 2:
            print("Need at least 2 versions to restore")
            return
        
        prev_version = versions[1]
        prev_obj = s3_client.get_object(
            Bucket=bucket_name,
            Key=object_key,
            VersionId=prev_version['VersionId']
        )
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key=object_key,
            Body=prev_obj['Body'].read()
        )
        
        print(f"Restored version {prev_version['VersionId']}")
        print(f"Date: {prev_version['LastModified'].strftime('%Y-%m-%d %H:%M:%S')}")
    
    except ClientError as e:
        print(f"Error: {e}")
 
 
def main():
    parser = argparse.ArgumentParser(description="S3 Versioning Management")
    parser.add_argument("-bn", "--bucket_name", type=str, required=True, help="Bucket name")
    parser.add_argument("-cv", "--check_versioning", action="store_true", help="Check versioning status")
    parser.add_argument("-k", "--key", type=str, help="Object key")
    parser.add_argument("-lv", "--list_versions", action="store_true", help="List object versions")
    parser.add_argument("-rv", "--restore_version", action="store_true", help="Restore previous version")
    
    args = parser.parse_args()
    s3_client = init_client()
    
    if args.check_versioning:
        check_versioning(s3_client, args.bucket_name)
    elif args.list_versions:
        if not args.key:
            print("Error: -k/--key required for listing versions")
            return
        list_versions(s3_client, args.bucket_name, args.key)
    elif args.restore_version:
        if not args.key:
            print("Error: -k/--key required for restoring version")
            return
        restore_version(s3_client, args.bucket_name, args.key)
 
 
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")