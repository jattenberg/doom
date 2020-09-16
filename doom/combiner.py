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

def get_optparser()
    parser = OptionParser(usage="take all the artist data and print to stdout")
    parser.add_option("-L",
                      "--log_level",
                      action="store",
                      dest="log_level",
                      default="INFO"
                      help="log level to use")

    return parser


def main():
    opt_parser = get_optparser()
    (options, args) = opt_parser.parse_args()

    q_listener, q = logger_init(options.log_level.upper())

    for x in list_bucket():
        print (read_object(x))

if __name__ == "__main__":
    main()
