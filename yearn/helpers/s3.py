import os
import shutil, json
from typing import List, TypedDict, Any

import boto3
from brownie import chain

print(boto3.__dict__)

class S3(TypedDict):
    s3: boto3.client
    aws_bucket: str
    
def get_s3s() -> List[S3]:
    s3s = []
    aws_buckets = os.environ.get("AWS_BUCKET").split(";")
    aws_endpoint_urls = os.environ.get("AWS_ENDPOINT_URL").split(";")
    aws_keys = os.environ.get("AWS_ACCESS_KEY").split(";")
    aws_secrets = os.environ.get("AWS_ACCESS_SECRET").split(";")

    for i in range(len(aws_buckets)):
        aws_bucket = aws_buckets[i]
        aws_endpoint_url = aws_endpoint_urls[i]
        aws_key = aws_keys[i]
        aws_secret = aws_secrets[i]
        kwargs = {}
        if aws_endpoint_url is not None:
            kwargs["endpoint_url"] = aws_endpoint_url
        if aws_key is not None:
            kwargs["aws_access_key_id"] = aws_key
        if aws_secret is not None:
            kwargs["aws_secret_access_key"] = aws_secret

        s3s.append(S3(s3=boto3.client("s3", **kwargs), aws_bucket=aws_bucket))
    return s3s

def get_export_paths(path_presufix: str, path_suffix: str):
    out = "generated"
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out, exist_ok=True)

    api_path = os.path.join("v1", "chains", f"{chain.id}", path_presufix)

    file_base_path = os.path.join(out, api_path)
    os.makedirs(file_base_path, exist_ok=True)

    file_name = os.path.join(file_base_path, path_suffix)
    s3_path = os.path.join(api_path, path_suffix)
    return file_name, s3_path

def upload(path_presufix: str, path_suffix: str, data: Any) -> None:
    print(json.dumps(data, sort_keys=True, indent=4))

    file_name, s3_path = get_export_paths(path_presufix, path_suffix)
    with open(file_name, "w+") as f:
        json.dump(data, f)

    if os.getenv("DEBUG", None):
        return

    for s3 in get_s3s():
        s3["s3"].upload_file(
            file_name,
            s3["aws_bucket"],
            s3_path,
            ExtraArgs={'ContentType': "application/json", 'CacheControl': "max-age=1800"},
        )