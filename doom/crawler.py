import sys
import os
import re
import string
import requests
import functools
import logging
import time
import warnings
import orjson
import boto3
import s3fs

import lyricsgenius as genius
import multiprocessing as mp
import pandas as pd

from optparse import OptionParser
from selenium import webdriver
from bs4.element import Tag
from bs4 import BeautifulSoup

from .utils import logger_init, worker_init

genius = genius.Genius(
    os.environ.get("GENIUS_ACCESS_TOKEN"),
    timeout=10,
    sleep_time=1
)

pattern = re.compile("api_path.*?/artists/(\d+)")
s3_client = boto3.client('s3')
s3 = s3fs.S3FileSystem()
lyrics_root = "genius-lyrics"

class Artist():
    def __init__(self, name, url, songs=[]):
        self.name = name
        self.url = url
        self.songs = songs
        self.artist_id = None

    def get_artist_id(self):
        html = fetch_with_retries(self.url)
        self.artist_id = pattern.findall(html)[0]

        logging.debug("got id: %s for artist %s" %
                      (self.artist_id, self.name))
        return self

    def get_songs(self):
        return self.songs

    def fetch_songs(self, attempt=0, attempts=5):
        try: 
            artist = genius.search_artist(self.name,
                                          allow_name_change=False,
                                          artist_id=self.artist_id)
            self.songs = [s.to_dict() for s in artist.songs]
            return self
        except Exception as e:
            if attempt < attempts:
                logging.info("retrying, on attempt %d" % (attempt+1))
                return self.fetch_songs(attempt+1)
            else:
                logging.error("unable to fetch %s, error: %s" %
                              (self.name, e))
                raise e

    def to_dict(self):
        return {
            "name": self.name,
            "url": self.url,
            "songs": self.songs,
            "artist_id": self.artist_id
        }
        

def get_and_scroll(url,
                   attempt=0,
                   attempts=5,
                   implicit_wait=30,
                   scroll_pause_time=3.5):
    """
    crawl the specified url and try to continually scroll
    to the bottom of the page in order to reveal any 
    'infinite scroll' elements
    """

    warnings.filterwarnings('ignore')
    # this throws a warning which i'm just ignoring for now
    driver = webdriver.PhantomJS()
    driver.implicitly_wait(implicit_wait)

    try:
        driver.get(url)

        last_height = driver.execute_script("return document.body.scrollHeight")

        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_pause_time)
            new_height = driver.execute_script("return document.body.scrollHeight")
            print ("last height: %d new height: %d" % (last_height, new_height))
            if new_height == last_height:
                break
            last_height = new_height

        return driver.page_source

    except Exception as e:
        if attempt < attempts:
            logging.info("retrying, on attept %d" % (attempt+1))
            return get_and_scroll(url, attempt+1)
        else:
            logging.error("unable to fetch %s, error: %s" % (url, e))
    finally:
        driver.quit()

def fetch_with_retries(url, attempt=0, attempts=5):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except Exception as e:
        if attempt < attempts:
            logging.info("retrying, on attept %d" % (attempt+1))
            return fetch_with_retries(url, attempt+1)
        else:
            logging.error("unable to fetch %s, error: %s" % (url, e))

def fetch_all_letters(
        base_url="https://genius.com/artists-index/%s/all?page=%d",
        letters=string.ascii_lowercase,
        processes=-1,
        pool=None):

    num_processes = processes if processes > 0 else mp.cpu_count()
    pool = pool if pool else mp.Pool(num_processes)

    artist_list = functools.reduce(
        lambda acc, x: acc + x,
        pool.imap_unordered(fetch_letter, letters),
        []
    )

    logging.info(">>>fetched all artists! %d total<<<"
                 % len(artist_list))
    return artist_list

def fetch_letter(
        letter,
        base_url="https://genius.com/artists-index/%s/all?page=%d",
        max_page=1000):

    pages = []
    total = 0
    for page in range(max_page):
        logging.debug("letter: %s, page: %d" % (letter, page))
        new_pages = fetch_letter_page(letter, page+1, base_url)
        
        links = len(new_pages)
        total = total + links
        logging.debug("page %s, got %d new links, %d total" %
                      (letter, links, total))

        if links < 1:
            logging.info("got up to page %d for letter %s" %
                         (page, letter))
            break

        pages = pages + new_pages

    return pages
        

def fetch_letter_page(
        letter,
        page,
        base_url="https://genius.com/artists-index/%s/all?page=%d"):

    url = base_url % (letter, page)
    html = fetch_with_retries(url)
    
    soup = BeautifulSoup(html, 'lxml')

    return [
        {
            "url": li.a['href'],
            "name": li.text.strip() # need to utf-8 encode to read
        } for li in 
        soup.find('ul', {'class': "artists_index_list"})
        if type(li) is Tag]

def fetch_all_artists(
        base_url="https://genius.com/artists-index/%s/all?page=%d",
        letters=string.ascii_lowercase,
        processes=-1,
        pool=None):
    
    artists_data = fetch_all_letters(base_url,
                                     letters,
                                     processes,
                                     pool)
    return [Artist(**artist) for artist in artists_data]

def fetch_songs_for_artist(artist):
    logging.debug("getting songs for %s" % artist.name)

    start = time.time()
    artist.fetch_songs()
    end = time.time()

    logging.debug("found %d songs for %s, took %0.1f"
                  % (artist.name,
                     len(artist.get_songs()),
                     end-start))

    return artist

def _recrawl_songs(a):
    object_path = "/%s/%s/%s" % (
        lyrics_root,
        a.name[0].lower(),
        "%s.json" % a.name
    )

    if s3.exists(object_path):
        logging.debug("already have %s" % a.name)
    else:
        logging.info("dont have %s, recrawling" % a.name)
        _get_and_save_songs(a)

def _get_and_save_songs(a):
    if not a.artist_id:
        logging.info("artist id, not present for %s, fetching" %
                     a.name)
        a.get_artist_id()

    a.fetch_songs() # get songs for the artist
    logging.debug("fetched %d songs for %s" %
                  (len(a.songs), a.name))
    json = orjson.dumps(a.to_dict())
    
    logging.debug("writing %s songs to s3" % a.name)
    s3_client.put_object(
        Body=json,
        Bucket=lyrics_root,
        Key= "%s/%s" % (a.name[0].lower(),
                        "%s.json" % a.name))
    logging.debug("done with %s" % a.name)

    # free up space?
    a.songs = None

def _get_ids(a):
    return a.get_artist_id()

def get_optparser():
    parser = OptionParser(usage="crawl artist and lyrics data from genius.com and store the results to amazon s3")

    parser.add_option("-p",
                      "--pool",
                      action="store",
                      dest="pool",
                      default=2*mp.cpu_count(),
                      help="size of pool of workers for parallel crawling")
    parser.add_option("-l",
                      "--letter",
                      action="store",
                      dest="letter",
                      default=None,
                      help="(optional) individual artist letter to get")
    parser.add_option("-r",
                      "--recrawl",
                      action="store_true",
                      dest="recrawl",
                      help="re-crawl any missing artists")

    parser.add_option("-L",
                      "--log_level",
                      action="store",
                      dest="log_level",
                      default="INFO",
                      help="log level to use")

    parser.add_option("-f",
                      "--file",
                      action="store",
                      dest="file",
                      default=None,
                      help="(optional) use this file of pre-stored artist data")

    parser.add_option("-o",
                      "--out",
                      action="store",
                      dest="out",
                      default=None,
                      help="(optional) where to write artist data")

    parser.add_option("-P",
                      "--pass",
                      action="store_true",
                      dest="no_crawl",
                      help="(optional) don't actually crawl songs")

    return parser

def main():
    opt_parser = get_optparser()
    (options, args) = opt_parser.parse_args()

    q_listener, q = logger_init(options.log_level.upper())

    pool = mp.Pool(int(options.pool),
                   worker_init,
                   [q])

    if options.file:
        logging.info("restoring artist info from disk: %s" %
                     options.file)
        with open(options.file, 'rb') as f:
            artists = [Artist(**a) for a in orjson.loads(f.read())]
        logging.info("got %d artists" % len(artists))
    elif options.letter:
        logging.info("getting %s artists" % options.letter)
        artists = [Artist(**a) for a in fetch_letter(options.letter)]
    else:
        logging.info("finding all artists")
        artists = fetch_all_artists(pool=pool)

    logging.info("done. got %d" % len(artists))

    if options.out:
        logging.info("writing artist data to %s" % options.out)
        with open(options.out, 'wb') as f:
            f.write(
                orjson.dumps([a.to_dict() for a in artists])
            )

    if options.no_crawl:
        logging.info("passing! see ya!")
    elif options.recrawl:
        logging.info("recrawling all artists")
        pool.imap_unordered(_recrawl_songs, artists)
    else:
        logging.info("getting songs and saving to s3")
        pool.imap_unordered(_get_and_save_songs, artists)

    logging.info("done")

    pool.close()
    pool.join()
    q_listener.stop()


if __name__ == "__main__":
    main()
