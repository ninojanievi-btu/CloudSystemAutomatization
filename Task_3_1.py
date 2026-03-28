import logging
import os
import mimetypes
from botocore.exceptions import ClientError
from auth import init_client
from bucket.crud import list_buckets, create_bucket, delete_bucket, bucket_exists
from bucket.policy import read_bucket_policy, assign_policy
from object.crud import download_file_and_upload_to_s3, get_objects, upload_file
from bucket.encryption import set_bucket_encryption, read_bucket_encryption
import argparse
 
# ============================================================================
# MULTIPART UPLOAD FUNCTIONS (Large File Upload)
# ============================================================================
 
PART_SIZE = 5 * 1024 * 1024  # 5 MB
 
 
def upload_large_file(s3_client, file_path, bucket_name):
    """
    Upload a large file using multipart upload.
    
    Args:
        s3_client: Boto3 S3 client
        file_path: Path to the file to upload
        bucket_name: Name of the S3 bucket
    
    Returns:
        bool: True if upload successful, False otherwise
    """
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return False
    
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    
    try:
        # Initiate multipart upload
        mpu = s3_client.create_multipart_upload(
            Bucket=bucket_name,
            Key=file_name
        )
        upload_id = mpu['UploadId']
        
        parts = []
        with open(file_path, 'rb') as f:
            part_number = 1
            while True:
                data = f.read(PART_SIZE)
                if not data:
                    break
                
                # Upload part
                part = s3_client.upload_part(
                    Body=data,
                    Bucket=bucket_name,
                    Key=file_name,
                    PartNumber=part_number,
                    UploadId=upload_id
                )
                
                parts.append({
                    'ETag': part['ETag'],
                    'PartNumber': part_number
                })
                
                # Print progress
                uploaded_size = part_number * PART_SIZE
                progress = min(100, (uploaded_size / file_size) * 100)
                print(f"Uploading part {part_number}... ({progress:.1f}%)")
                
                part_number += 1
        
        # Complete multipart upload
        s3_client.complete_multipart_upload(
            Bucket=bucket_name,
            Key=file_name,
            UploadId=upload_id,
            MultipartUpload={'Parts': parts}
        )
        
        print(f"Successfully uploaded {file_name} ({file_size / (1024*1024):.2f} MB)")
        return True
        
    except ClientError as e:
        print(f"Error uploading file: {e}")
        # Abort upload on error
        if 'upload_id' in locals():
            s3_client.abort_multipart_upload(
                Bucket=bucket_name,
                Key=file_name,
                UploadId=upload_id
            )
        return False
 
 
# ============================================================================
# MIME TYPE VALIDATION FUNCTIONS
# ============================================================================
 
def validate_mimetype(file_path, allowed_mimetypes=None):
    """
    Validate MIME type of a file.
    
    Args:
        file_path: Path to the file to validate
        allowed_mimetypes: List of allowed MIME types. 
                          If None, allows all MIME types.
                          Example: ['image/jpeg', 'image/png', 'application/pdf']
    
    Returns:
        bool: True if MIME type is valid, False otherwise
    """
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return False
    
    # Get MIME type
    mime_type, _ = mimetypes.guess_type(file_path)
    
    if mime_type is None:
        print(f"Warning: Could not determine MIME type for {file_path}")
        return True  # Allow unknown MIME types
    
    print(f"Detected MIME type: {mime_type}")
    
    # If no allowed types specified, allow all
    if allowed_mimetypes is None:
        print(f"MIME type validation passed (no restrictions)")
        return True
    
    # Check if MIME type is in allowed list
    if mime_type in allowed_mimetypes:
        print(f"MIME type validation passed: {mime_type}")
        return True
    
    print(f"MIME type validation failed: {mime_type} not in allowed types {allowed_mimetypes}")
    return False
 
 
# ============================================================================
# LIFECYCLE POLICY FUNCTIONS
# ============================================================================
 
def set_lifecycle_policy(s3_client, bucket_name, days=120):
    """
    Set lifecycle policy to delete objects after specified number of days.
    
    Args:
        s3_client: Boto3 S3 client
        bucket_name: Name of the S3 bucket
        days: Number of days after which to delete objects (default: 120)
    
    Returns:
        bool: True if policy set successfully, False otherwise
    """
    try:
        lifecycle_policy = {
            'Rules': [
                {
                    'ID': f'delete-after-{days}-days',
                    'Status': 'Enabled',
                    'Prefix': '',  # Apply to all objects
                    'Expiration': {
                        'Days': days
                    }
                }
            ]
        }
        
        s3_client.put_bucket_lifecycle_configuration(
            Bucket=bucket_name,
            LifecycleConfiguration=lifecycle_policy
        )
        
        print(f"Lifecycle policy set for bucket '{bucket_name}'")
        print(f"Objects will be deleted after {days} days of creation")
        return True
        
    except ClientError as e:
        print(f"Error setting lifecycle policy: {e}")
        return False
 
 
def read_lifecycle_policy(s3_client, bucket_name):
    """
    Read lifecycle policy from a bucket.
    
    Args:
        s3_client: Boto3 S3 client
        bucket_name: Name of the S3 bucket
    
    Returns:
        dict or None: Lifecycle policy configuration, or None if not set
    """
    try:
        response = s3_client.get_bucket_lifecycle_configuration(
            Bucket=bucket_name
        )
        
        print(f"Lifecycle policy for bucket '{bucket_name}':")
        print("-" * 50)
        
        for rule in response.get('Rules', []):
            print(f"Rule ID: {rule.get('ID')}")
            print(f"Status: {rule.get('Status')}")
            print(f"Prefix: {rule.get('Prefix', '')}")
            
            if 'Expiration' in rule:
                days = rule['Expiration'].get('Days')
                print(f"Expiration: Delete after {days} days")
            
            if 'NoncurrentVersionExpiration' in rule:
                days = rule['NoncurrentVersionExpiration'].get('NoncurrentDays')
                print(f"Noncurrent Version Expiration: Delete after {days} days")
            
            print()
        
        return response
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchLifecycleConfiguration':
            print(f"No lifecycle policy configured for bucket '{bucket_name}'")
        else:
            print(f"Error reading lifecycle policy: {e}")
        return None
 
parser = argparse.ArgumentParser(
    description="CLI program that helps with S3 buckets.",
    usage="""
    How to download and upload directly:
    short:
        python main.py -bn new-bucket-btu-7 -ol https://cdn.activestate.com/wp-content/uploads/2021/12/python-coding-mistakes.jpg -du
    long:
       python main.py  --bucket_name new-bucket-btu-7 --object_link https://cdn.activestate.com/wp-content/uploads/2021/12/python-coding-mistakes.jpg --download_upload
 
    How to list buckets:
    short:
        python main.py -lb
    long:
        python main.py --list_buckets
 
    How to create bucket:
    short:
        -bn new-bucket-btu-1 -cb -region us-west-2
    long:
        --bucket_name new-bucket-btu-1 --create_bucket --region us-west-2
 
    How to assign missing policy:
    short:
        -bn new-bucket-btu-1 -amp
    long:
        --bn new-bucket-btu-1 --assign_missing_policy
 
    How to upload small file:
    short:
        python main.py -bn my-bucket -uf path/to/file.txt
    long:
        python main.py --bucket_name my-bucket --upload_file path/to/file.txt
 
    How to upload large file:
    short:
        python main.py -bn my-bucket -ulf path/to/largefile.zip
    long:
        python main.py --bucket_name my-bucket --upload_large_file path/to/largefile.zip
 
    How to upload with MIME type validation:
    short:
        python main.py -bn my-bucket -uf file.pdf -vm
    long:
        python main.py --bucket_name my-bucket --upload_file file.pdf --validate_mime
 
    How to set lifecycle policy (delete after 120 days):
    short:
        python main.py -bn my-bucket -slp
    long:
        python main.py --bucket_name my-bucket --set_lifecycle_policy
 
    How to read lifecycle policy:
    short:
        python main.py -bn my-bucket -rlp
    long:
        python main.py --bucket_name my-bucket --read_lifecycle_policy
    """,
    prog="main.py",
    epilog="DEMO APP FOR BTU_AWS",
)
 
parser.add_argument(
    "-lb",
    "--list_buckets",
    help="List already created buckets.",
    # https://docs.python.org/dev/library/argparse.html#action
    action="store_true",
)
 
parser.add_argument(
    "-cb",
    "--create_bucket",
    help="Flag to create bucket.",
    choices=["False", "True"],
    type=str,
    nargs="?",
    # https://jdhao.github.io/2018/10/11/python_argparse_set_boolean_params
    const="True",
    default="False",
)
 
parser.add_argument(
    "-bn", "--bucket_name", type=str, help="Pass bucket name.", default=None
)
 
parser.add_argument(
    "-bc",
    "--bucket_check",
    help="Check if bucket already exists.",
    choices=["False", "True"],
    type=str,
    nargs="?",
    const="True",
    default="True",
)
 
parser.add_argument(
    "-region", "--region", type=str, help="Region variable.", default=None
)
 
parser.add_argument(
    "-db",
    "--delete_bucket",
    help="flag to delete bucket",
    choices=["False", "True"],
    type=str,
    nargs="?",
    const="True",
    default="False",
)
 
parser.add_argument(
    "-be",
    "--bucket_exists",
    help="flag to check if bucket exists",
    choices=["False", "True"],
    type=str,
    nargs="?",
    const="True",
    default="False",
)
 
parser.add_argument(
    "-rp",
    "--read_policy",
    help="flag to read bucket policy.",
    choices=["False", "True"],
    type=str,
    nargs="?",
    const="True",
    default="False",
)
 
parser.add_argument(
    "-arp",
    "--assign_read_policy",
    help="flag to assign read bucket policy.",
    choices=["False", "True"],
    type=str,
    nargs="?",
    const="True",
    default="False",
)
 
parser.add_argument(
    "-amp",
    "--assign_missing_policy",
    help="flag to assign read bucket policy.",
    choices=["False", "True"],
    type=str,
    nargs="?",
    const="True",
    default="False",
)
 
parser.add_argument(
    "-du",
    "--download_upload",
    choices=["False", "True"],
    help="download and upload to bucket",
    type=str,
    nargs="?",
    const="True",
    default="False",
)
 
parser.add_argument(
    "-ol",
    "--object_link",
    type=str,
    help="link to download and upload to bucket",
    default=None,
)
 
parser.add_argument(
    "-lo",
    "--list_objects",
    type=str,
    help="list bucket object",
    nargs="?",
    const="True",
    default="False",
)
 
parser.add_argument(
    "-ben",
    "--bucket_encryption",
    type=str,
    help="bucket object encryption",
    nargs="?",
    const="True",
    default="False",
)
 
parser.add_argument(
    "-rben",
    "--read_bucket_encryption",
    type=str,
    help="list bucket object",
    nargs="?",
    const="True",
    default="False",
)
 
parser.add_argument(
    "-uf",
    "--upload_file",
    type=str,
    help="Upload small file",
    nargs="?",
    const="True",
    default="False",
)
 
parser.add_argument(
    "-ulf",
    "--upload_large_file",
    type=str,
    help="Upload large file using multipart upload",
    nargs="?",
    const="True",
    default="False",
)
 
parser.add_argument(
    "-vm",
    "--validate_mime",
    help="Validate MIME type during upload",
    choices=["False", "True"],
    type=str,
    nargs="?",
    const="True",
    default="False",
)
 
parser.add_argument(
    "-slp",
    "--set_lifecycle_policy",
    help="Set lifecycle policy to delete objects after 120 days",
    choices=["False", "True"],
    type=str,
    nargs="?",
    const="True",
    default="False",
)
 
parser.add_argument(
    "-rlp",
    "--read_lifecycle_policy",
    help="Read lifecycle policy from bucket",
    choices=["False", "True"],
    type=str,
    nargs="?",
    const="True",
    default="False",
)
 
parser.add_argument(
    "-allowed-mimes",
    "--allowed_mimetypes",
    type=str,
    help="Comma-separated list of allowed MIME types (e.g., 'image/jpeg,image/png,application/pdf')",
    default=None,
)
 
 
def main():
    s3_client = init_client()
    args = parser.parse_args()
 
    if args.bucket_name:
        if args.create_bucket == "True":
            if not args.region:
                parser.error("Please provide region for bucket --region REGION_NAME")
            if (args.bucket_check == "True") and bucket_exists(
                s3_client, args.bucket_name
            ):
                parser.error("Bucket already exists")
            if create_bucket(s3_client, args.bucket_name, args.region):
                print("Bucket successfully created")
 
        if (args.delete_bucket == "True") and delete_bucket(
            s3_client, args.bucket_name
        ):
            print("Bucket successfully deleted")
 
        if args.bucket_exists == "True":
            print(f"Bucket exists: {bucket_exists(s3_client, args.bucket_name)}")
 
        if args.read_policy == "True":
            print(read_bucket_policy(s3_client, args.bucket_name))
 
        if args.assign_read_policy == "True":
            assign_policy(s3_client, "public_read_policy", args.bucket_name)
 
        if args.assign_missing_policy == "True":
            assign_policy(s3_client, "multiple_policy", args.bucket_name)
 
        if args.object_link:
            if args.download_upload == "True":
                print(
                    download_file_and_upload_to_s3(
                        s3_client, args.bucket_name, args.object_link
                    )
                )
        if args.bucket_encryption == "True":
            if set_bucket_encryption(s3_client, args.bucket_name):
                print("Encryption set")
        if args.read_bucket_encryption == "True":
            print(read_bucket_encryption(s3_client, args.bucket_name))
 
        if args.list_objects == "True":
            get_objects(s3_client, args.bucket_name)
 
        # Small file upload
        if args.upload_file and args.upload_file != "False":
            if args.validate_mime == "True":
                allowed_mimes = None
                if args.allowed_mimetypes:
                    allowed_mimes = [mime.strip() for mime in args.allowed_mimetypes.split(",")]
                
                if validate_mimetype(args.upload_file, allowed_mimes):
                    upload_file(s3_client, args.upload_file, args.bucket_name)
                    print(f"File {args.upload_file} successfully uploaded")
                else:
                    print(f"MIME type validation failed for {args.upload_file}")
            else:
                upload_file(s3_client, args.upload_file, args.bucket_name)
                print(f"File {args.upload_file} successfully uploaded")
 
        # Large file upload
        if args.upload_large_file and args.upload_large_file != "False":
            if args.validate_mime == "True":
                allowed_mimes = None
                if args.allowed_mimetypes:
                    allowed_mimes = [mime.strip() for mime in args.allowed_mimetypes.split(",")]
                
                if validate_mimetype(args.upload_large_file, allowed_mimes):
                    upload_large_file(s3_client, args.upload_large_file, args.bucket_name)
                    print(f"Large file {args.upload_large_file} successfully uploaded")
                else:
                    print(f"MIME type validation failed for {args.upload_large_file}")
            else:
                upload_large_file(s3_client, args.upload_large_file, args.bucket_name)
                print(f"Large file {args.upload_large_file} successfully uploaded")
 
        # Set lifecycle policy
        if args.set_lifecycle_policy == "True":
            if set_lifecycle_policy(s3_client, args.bucket_name, days=120):
                print("Lifecycle policy set: Objects will be deleted after 120 days")
 
        # Read lifecycle policy
        if args.read_lifecycle_policy == "True":
            policy = read_lifecycle_policy(s3_client, args.bucket_name)
            if policy:
                print(policy)
 
    if args.list_buckets:
        buckets = list_buckets(s3_client)
        if buckets:
            for bucket in buckets["Buckets"]:
                print(f'  {bucket["Name"]}')
 
 
if __name__ == "__main__":
    try:
        main()
    except ClientError as e:
        logging.error(e)