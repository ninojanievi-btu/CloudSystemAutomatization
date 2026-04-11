import argparse, os, sys
from datetime import datetime, timedelta
 
def get_versions(file_path):
    """Get all versions of a file"""
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found")
        return []
    
    base = os.path.splitext(file_path)[0]
    ext = os.path.splitext(file_path)[1]
    versions = []
    
    for fname in os.listdir(os.path.dirname(file_path) or "."):
        if fname.startswith(os.path.basename(base)) and fname.endswith(ext):
            full_path = os.path.join(os.path.dirname(file_path) or ".", fname)
            mtime = os.path.getmtime(full_path)
            versions.append((full_path, datetime.fromtimestamp(mtime)))
    
    return sorted(versions, key=lambda x: x[1], reverse=True)
 
def delete_old(file_path, months=6, dry_run=False):
    """Delete versions older than months"""
    versions = get_versions(file_path)
    
    if not versions:
        print(f"No versions found for {file_path}")
        return
    
    cutoff = datetime.now() - timedelta(days=months*30)
    deleted = 0
    
    print(f"Versions of {os.path.basename(file_path)}:")
    for fpath, mtime in versions:
        age = (datetime.now() - mtime).days
        status = "DELETE" if mtime < cutoff else "KEEP"
        print(f"  {status} ({age}d) {os.path.basename(fpath)}")
        
        if mtime < cutoff and not dry_run:
            try:
                os.remove(fpath)
                deleted += 1
            except Exception as e:
                print(f"    Error: {e}")
    
    print(f"Deleted: {deleted} versions")
 
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check and delete old file versions")
    parser.add_argument("files", nargs="+", help="File paths to check")
    parser.add_argument("-m", "--months", type=int, default=6, help="Delete versions older than X months")
    parser.add_argument("--dry-run", action="store_true", help="Preview without deleting")
    args = parser.parse_args()
    
    for file in args.files:
        delete_old(file, args.months, args.dry_run)
        print()
 