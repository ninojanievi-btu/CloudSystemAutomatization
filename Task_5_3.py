import json
import boto3
import os

s3 = boto3.client('s3')

EXTENSION_MAP = {
    "jpg": "images/",
    "jpeg": "images/",
    "png": "images/",
    "gif": "images/",
    "pdf": "documents/",
    "txt": "documents/",
    "csv": "data/",
    "json": "data/"
}

def lambda_handler(event, context):
    print("Event:", json.dumps(event))

    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']

    # file extension
    extension = key.split('.')[-1].lower()

    folder = EXTENSION_MAP.get(extension, "others/")

    new_key = folder + os.path.basename(key)

    print(f"Moving {key} → {new_key}")

    # copy
    s3.copy_object(
        Bucket=bucket,
        CopySource={'Bucket': bucket, 'Key': key},
        Key=new_key
    )

    # delete old
    s3.delete_object(
        Bucket=bucket,
        Key=key
    )

    return {
        "statusCode": 200,
        "body": f"File moved to {new_key}"
    }