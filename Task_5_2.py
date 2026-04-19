import argparse
import requests
import json
import boto3
from datetime import datetime

s3 = boto3.client("s3")


# -----------------------
# QUOTE FETCHING
# -----------------------
def get_quote(author=None):
    base_url = "https://api.quotable.kurokeita.dev"

    if author:
        url = f"{base_url}/quotes?author={author}"
        response = requests.get(url)
        data = response.json()

        if not data["results"]:
            raise Exception("No quotes found for this author")

        quote = data["results"][0]
    else:
        url = f"{base_url}/random"
        response = requests.get(url)
        quote = response.json()

    return {
        "content": quote["content"],
        "author": quote["author"]
    }


# -----------------------
# SAVE TO S3
# -----------------------
def save_to_s3(bucket, quote):
    filename = f"quote_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    s3.put_object(
        Bucket=bucket,
        Key=filename,
        Body=json.dumps(quote, indent=2),
        ContentType="application/json"
    )

    return filename


# -----------------------
# CLI
# -----------------------
def main():
    parser = argparse.ArgumentParser(description="Inspire CLI Tool")

    parser.add_argument("bucket_name", help="S3 bucket name")

    parser.add_argument(
        "--inspire",
        nargs="?",
        const=True,
        help="Get random quote or quote by author"
    )

    parser.add_argument(
        "--save",
        action="store_true",
        help="Save quote to S3 bucket"
    )

    args = parser.parse_args()

    if args.inspire is not None:
        author = None if args.inspire is True else args.inspire

        quote = get_quote(author)

        print(f'\n"{quote["content"]}"')
        print(f'— {quote["author"]}\n')

        if args.save:
            filename = save_to_s3(args.bucket_name, quote)
            print(f"✅ Saved to S3 as {filename}")


if __name__ == "__main__":
    main()