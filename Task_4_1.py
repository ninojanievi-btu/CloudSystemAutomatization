import argparse, os, magic, boto3
 
MIME = {"image": "images", "video": "videos", "audio": "audio", "text": "text", "application/pdf": "docs"}
 
def get_folder(mime): return MIME.get(mime, MIME.get(mime.split("/")[0], "other"))
 
def upload(file, bucket, region="us-east-1"):
    if not os.path.exists(file): print(f"Error: {file} not found"); return False
    mime = magic.Magic(mime=True).from_file(file)
    key = f"{get_folder(mime)}/{os.path.basename(file)}"
    try:
        boto3.client("s3", region_name=region).upload_file(file, bucket, key)
        print(f"✓ s3://{bucket}/{key}"); return True
    except Exception as e: print(f"Error: {e}"); return False
 
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload file to S3 by type")
    parser.add_argument("-f", "--file", required=True)
    parser.add_argument("-b", "--bucket", required=True)
    parser.add_argument("-r", "--region", default="us-east-1")
    args = parser.parse_args()
    exit(0 if upload(args.file, args.bucket, args.region) else 1)