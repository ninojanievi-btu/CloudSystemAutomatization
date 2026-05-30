import boto3
import argparse
import mimetypes
import os
import sys
import json
import urllib.request
import urllib.parse
import urllib.error
import datetime
from os import getenv

s3_client = boto3.client(
    "s3",
    aws_access_key_id=getenv("aws_access_key_id"),
    aws_secret_access_key=getenv("aws_secret_access_key"),
    aws_session_token=getenv("aws_session_token"),
    region_name=getenv("aws_region_name", "us-east-1"),
)

REGION = getenv("aws_region_name", "us-east-1")
QUOTES_API = "https://api.quotable.kurokeita.dev"


# ══════════════════════════════════════════════
#  QUOTE HELPERS
# ══════════════════════════════════════════════

def fetch_random_quote():
    """Fetch a completely random quote."""
    url = f"{QUOTES_API}/quotes/random"
    return _get_json(url)


def fetch_quote_by_author(author):
    """
    Fetch a random quote filtered by author name.
    Uses /quotes?author=<name>&limit=1 then picks the first result,
    falling back to /quotes/random?author=<name> if supported.
    """
    encoded = urllib.parse.quote(author)
    url = f"{QUOTES_API}/quotes?author={encoded}&limit=1"
    data = _get_json(url)

    # The API returns { results: [...], ... } for list endpoints
    results = data.get("results") or data.get("quotes") or data.get("data")
    if results and len(results) > 0:
        return results[0]

    # Some versions wrap differently — try random with author param
    url2 = f"{QUOTES_API}/quotes/random?author={encoded}"
    return _get_json(url2)


def _get_json(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        print(f"      ERROR: API returned HTTP {e.code} for {url}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"      ERROR: Could not reach API — {e.reason}")
        sys.exit(1)


def print_quote(quote):
    """Pretty-print a quote dict."""
    content = quote.get("content") or quote.get("quote") or quote.get("text", "")
    author  = quote.get("author") or quote.get("authorName") or "Unknown"
    print(f'\n  "{content}"\n      — {author}\n')
    return content, author


# ══════════════════════════════════════════════
#  S3 HELPERS  (from previous task)
# ══════════════════════════════════════════════

def create_bucket(bucket_name):
    print(f"\n[1/4] Creating bucket '{bucket_name}'...")
    try:
        if REGION == "us-east-1":
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )
        print(f"      Bucket created.")
    except s3_client.exceptions.BucketAlreadyOwnedByYou:
        print(f"      Bucket already exists and is owned by you — reusing it.")
    except Exception as e:
        print(f"      ERROR creating bucket: {e}")
        sys.exit(1)


def upload_files(bucket_name, source_folder):
    print(f"\n[2/4] Uploading files from '{source_folder}'...")
    if not os.path.isdir(source_folder):
        print(f"      ERROR: Source folder '{source_folder}' does not exist.")
        sys.exit(1)
    uploaded = 0
    for root, dirs, files in os.walk(source_folder):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for filename in files:
            if filename.startswith("."):
                continue
            local_path = os.path.join(root, filename)
            s3_key = os.path.relpath(local_path, source_folder).replace("\\", "/")
            content_type, _ = mimetypes.guess_type(local_path)
            if content_type is None:
                content_type = "application/octet-stream"
            s3_client.upload_file(local_path, bucket_name, s3_key,
                                  ExtraArgs={"ContentType": content_type})
            print(f"      Uploaded: {s3_key} ({content_type})")
            uploaded += 1
    print(f"      Total files uploaded: {uploaded}")


def configure_website(bucket_name, index_doc, error_doc):
    print(f"\n[3/4] Configuring WebsiteConfiguration...")
    s3_client.put_bucket_website(
        Bucket=bucket_name,
        WebsiteConfiguration={
            "IndexDocument": {"Suffix": index_doc},
            "ErrorDocument": {"Key": error_doc},
        },
    )
    print(f"      Index: {index_doc} | Error: {error_doc}")


def set_public_access(bucket_name):
    print(f"\n[4/4] Setting public access permissions...")
    s3_client.put_public_access_block(
        Bucket=bucket_name,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": False,
            "IgnorePublicAcls": False,
            "BlockPublicPolicy": False,
            "RestrictPublicBuckets": False,
        },
    )
    policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": f"arn:aws:s3:::{bucket_name}/*",
        }],
    }
    s3_client.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))
    print(f"      Public read policy applied.")


def get_website_url(bucket_name):
    if REGION == "us-east-1":
        return f"http://{bucket_name}.s3-website-us-east-1.amazonaws.com"
    return f"http://{bucket_name}.s3-website.{REGION}.amazonaws.com"


def ensure_bucket_exists(bucket_name):
    """Create bucket only if it doesn't exist yet (for --save without --source)."""
    try:
        s3_client.head_bucket(Bucket=bucket_name)
    except Exception:
        try:
            if REGION == "us-east-1":
                s3_client.create_bucket(Bucket=bucket_name)
            else:
                s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": REGION},
                )
            # make bucket private by default for quote storage
            print(f"      Bucket '{bucket_name}' created.")
        except Exception as e:
            print(f"      ERROR creating bucket: {e}")
            sys.exit(1)


def save_quote_to_s3(bucket_name, quote):
    """Upload quote as a timestamped JSON file to the bucket."""
    ensure_bucket_exists(bucket_name)

    content = quote.get("content") or quote.get("quote") or quote.get("text", "")
    author  = quote.get("author") or quote.get("authorName") or "Unknown"

    payload = {
        "content": content,
        "author": author,
        "saved_at": datetime.datetime.utcnow().isoformat() + "Z",
        "raw": quote,
    }

    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_author = author.replace(" ", "_").replace("/", "-")
    key = f"quotes/{safe_author}_{timestamp}.json"

    s3_client.put_object(
        Bucket=bucket_name,
        Key=key,
        Body=json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )
    print(f"      Saved to s3://{bucket_name}/{key}")
    return key


# ══════════════════════════════════════════════
#  COMMANDS
# ══════════════════════════════════════════════

def cmd_host(args):
    create_bucket(args.bucket)
    upload_files(args.bucket, args.source)
    configure_website(args.bucket, args.index, args.error)
    set_public_access(args.bucket)
    url = get_website_url(args.bucket)
    print(f"\n{'='*55}")
    print(f"  Static website is live!")
    print(f"  URL: {url}")
    print(f"{'='*55}\n")


def cmd_inspire(args):
    author = args.inspire  # None = random, str = filter by author

    if author:
        print(f"\n[+] Fetching quote by '{author}'...")
        quote = fetch_quote_by_author(author)
    else:
        print(f"\n[+] Fetching random quote...")
        quote = fetch_random_quote()

    print_quote(quote)

    if args.save:
        bucket_name = args.bucket
        if not bucket_name:
            print("ERROR: provide a bucket name as first argument when using --save")
            print("  Usage: python main.py inspire --inspire \"Author\" --save --bucket my-bucket")
            sys.exit(1)
        print(f"[+] Saving quote to S3 bucket '{bucket_name}'...")
        save_quote_to_s3(bucket_name, quote)
        print(f"      Done.\n")


# ══════════════════════════════════════════════
#  CLI SETUP
# ══════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="AWS S3 toolkit — host static sites and save quotes."
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    # ── host ──────────────────────────────────
    host_parser = subparsers.add_parser(
        "host",
        help="Upload a local folder to S3 and enable static website hosting."
    )
    host_parser.add_argument("bucket", help="S3 bucket name (globally unique)")
    host_parser.add_argument("--source", required=True, metavar="FOLDER",
                             help="Local folder with website files")
    host_parser.add_argument("--index", default="index.html",
                             help="Index document (default: index.html)")
    host_parser.add_argument("--error", default="404.html",
                             help="Error document (default: 404.html)")
    host_parser.set_defaults(func=cmd_host)

    # ── inspire ───────────────────────────────
    inspire_parser = subparsers.add_parser(
        "inspire",
        help="Fetch a quote from the Quotable API."
    )
    inspire_parser.add_argument(
        "bucket", nargs="?", default=None,
        help="S3 bucket name — required when using --save"
    )
    inspire_parser.add_argument(
        "--inspire", nargs="?", const=True, default=True, metavar="AUTHOR",
        help=(
            "Fetch a random quote (no value), "
            "or a quote by a specific author: --inspire \"Linus Torvalds\""
        )
    )
    inspire_parser.add_argument(
        "--save", action="store_true",
        help="Save the quote as a .json file to the given S3 bucket"
    )
    inspire_parser.set_defaults(func=cmd_inspire)

    args = parser.parse_args()

    # Normalise --inspire: if it's True (flag with no value) treat as random
    if hasattr(args, "inspire") and args.inspire is True:
        args.inspire = None  # random mode

    args.func(args)


if __name__ == "__main__":
    main()
