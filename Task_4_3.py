import argparse, os, sys, boto3
from datetime import datetime, timedelta
 
s3 = boto3.client("s3")
 
def check_versioning(bucket):
    """Check if S3 bucket has versioning enabled"""
    try:
        response = s3.get_bucket_versioning(Bucket=bucket)
        status = response.get("Status", "Disabled")
        print(f"Bucket: {bucket}")
        print(f"Versioning: {'✓ Enabled' if status == 'Enabled' else '✗ Disabled'}")
    except Exception as e:
        print(f"Error: {e}")
 
def list_versions(bucket, key):
    """List all versions of a file"""
    try:
        response = s3.list_object_versions(Bucket=bucket, Prefix=key)
        versions = response.get("Versions", [])
        
        if not versions:
            print(f"No versions found for {key}")
            return
        
        print(f"Versions of {key} ({len(versions)} total):")
        for v in versions:
            date = v["LastModified"].strftime("%Y-%m-%d %H:%M:%S")
            vid = v["VersionId"]
            print(f"  {date} | {vid}")
    except Exception as e:
        print(f"Error: {e}")
 
def restore_previous(bucket, key):
    """Restore previous version as new version"""
    try:
        response = s3.list_object_versions(Bucket=bucket, Prefix=key)
        versions = response.get("Versions", [])
        
        if len(versions) < 2:
            print(f"Need at least 2 versions to restore")
            return
        
        # Get second newest version
        prev_version = versions[1]["VersionId"]
        
        # Get previous version object
        obj = s3.get_object(Bucket=bucket, Key=key, VersionId=prev_version)
        body = obj["Body"].read()
        
        # Upload as new version
        s3.put_object(Bucket=bucket, Key=key, Body=body)
        
        print(f"✓ Restored previous version as new version")
        print(f"  Previous version ID: {prev_version}")
    except Exception as e:
        print(f"Error: {e}")
 
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="S3 file versioning tool")
    parser.add_argument("-b", "--bucket", help="S3 bucket name")
    parser.add_argument("-k", "--key", help="File key in bucket")
    parser.add_argument("--check-versioning", action="store_true", help="Check if versioning enabled")
    parser.add_argument("--list-versions", action="store_true", help="List all versions of file")
    parser.add_argument("--restore-previous", action="store_true", help="Restore previous version as new")
    
    args = parser.parse_args()
    
    if args.check_versioning and args.bucket:
        check_versioning(args.bucket)
    elif args.list_versions and args.bucket and args.key:
        list_versions(args.bucket, args.key)
    elif args.restore_previous and args.bucket and args.key:
        restore_previous(args.bucket, args.key)
    else:
        parser.print_help()