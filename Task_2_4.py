import os
import json
from pathlib import Path
from dotenv import load_dotenv
import boto3
import typer
import magic
from botocore.exceptions import ClientError
 
load_dotenv()
 
app = typer.Typer()
s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
)
 
ALLOWED_TYPES = {'image/bmp', 'image/jpeg', 'image/png', 'image/webp', 'video/mp4'}
 
def init_client():
    return s3
 
def bucket_exists(bucket_name: str) -> bool:
    try:
        s3.head_bucket(Bucket=bucket_name)
        return True
    except:
        return False
 
@app.command()
def list_buckets():
    """List all buckets."""
    buckets = s3.list_buckets()['Buckets']
    for b in buckets:
        typer.echo(f"  - {b['Name']}")
 
@app.command()
def create_bucket(bucket_name: str):
    """Create bucket."""
    try:
        s3.create_bucket(Bucket=bucket_name)
        typer.echo(f"Bucket '{bucket_name}' created!")
    except Exception as e:
        typer.echo(f"Error: {e}")
 
@app.command()
def delete_bucket(bucket_name: str):
    """Delete bucket."""
    try:
        if not bucket_exists(bucket_name):
            typer.echo(f"Bucket '{bucket_name}' does not exist!")
            return
        s3.delete_bucket(Bucket=bucket_name)
        typer.echo(f"Bucket '{bucket_name}' deleted!")
    except Exception as e:
        typer.echo(f"Error: {e}")
 
@app.command()
def download_and_upload(bucket_name: str, file_path: str, s3_key: str):
    """Upload file (validates .bmp, .jpg, .jpeg, .png, .webp, .mp4)."""
    try:
        if not Path(file_path).exists():
            typer.echo(f"File not found!")
            return
        
        mime = magic.Magic(mime=True)
        file_mime = mime.from_file(file_path)
        
        if file_mime not in ALLOWED_TYPES:
            typer.echo(f"Invalid file type! Allowed: .bmp, .jpg, .jpeg, .png, .webp, .mp4")
            return
        
        s3.upload_file(file_path, bucket_name, s3_key)
        typer.echo(f"File uploaded to s3://{bucket_name}/{s3_key}")
    except Exception as e:
        typer.echo(f"Error: {e}")
 
def generate_public_read_policy(bucket_name: str, folders: list) -> dict:
    """Generate public read policy."""
    resources = [f"arn:aws:s3:::{bucket_name}/{f}/*" for f in folders]
    return {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": resources
        }]
    }
 
@app.command()
def set_object_access_policy(bucket_name: str, folders: str = "dev,test"):
    """Set public read policy for folders."""
    try:
        folder_list = [f.strip() for f in folders.split(',')]
        policy = generate_public_read_policy(bucket_name, folder_list)
        create_bucket_policy(bucket_name, policy)
    except Exception as e:
        typer.echo(f"Error: {e}")
 
@app.command()
def create_bucket_policy(bucket_name: str, policy: dict = None):
    """Create bucket policy."""
    try:
        if policy is None:
            policy = generate_public_read_policy(bucket_name, ['dev', 'test'])
        s3.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))
        typer.echo(f"Policy created for '{bucket_name}'!")
    except Exception as e:
        typer.echo(f"Error: {e}")
 
@app.command()
def read_bucket_policy(bucket_name: str):
    """Read bucket policy."""
    try:
        response = s3.get_bucket_policy(Bucket=bucket_name)
        policy = json.loads(response['Policy'])
        typer.echo(json.dumps(policy, indent=2))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchBucketPolicy':
            typer.echo(f"No policy found!")
        else:
            typer.echo(f"Error: {e}")
 
if __name__ == "__main__":
    app()