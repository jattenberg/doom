import boto3
import orjson
import sys
import logging

from .utils import logger_init, worker_init

lyrics_root = "genius-lyrics"
s3 = boto3.resource('s3')

def list_bucket():
    bucket = s3.Bucket(lyrics_root)
    return bucket.objects.all()

def read_object(obj):
    return orjson.loads(obj.get()['Body'].read())

def main():
    q_listener, q = logger_init(logging.INFO)

    for x in list_bucket():
        print (read_object(x))

if __name__ == "__main__":
    main()
