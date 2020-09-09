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

import multiprocessing as mp
import lyricsgenius as genius
import pandas as pd
from selenium import webdriver
from bs4.element import Tag
from bs4 import BeautifulSoup

genius = genius.Genius(os.environ.get("GENIUS_ACCESS_TOKEN"))
pattern = re.compile("api_path.*?/artists/(\d+)")
s3_client = boto3.client('s3')
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
            self.artist = genius.search_artist(self.name,
                                               allow_name_change=False,
                                               artist_id=self.artist_id)
            return self
        except Exception as e:
            if attempt < attempts:
                logging.info("retrying, on attept %d" % (attempt+1))
                return self.fetch_songs(attepmt+1)
            else:
                logging.error("unable to fetch %s, error: %s" % (url, e))
        

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
        processes=-1):

    pool = mp.Pool(processes if processes > 0 else mp.cpu_count())

    artist_list = functools.reduce(
        lambda acc, x: acc + x,
        pool.map(fetch_letter, letters),
        [])

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
        letters=string.ascii_lowercase):
    
    artists_data = fetch_all_letters(base_url, letters)
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

def fetch_songs_for_artists(artists):
    pass

def _get_songs(a):
    return a.fetch_songs()


def _get_ids(a):
    return a.get_artist_id()

def main():
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
        level="DEBUG",
    )

    base_dir = "./data"

    """
    all_artists = fetch_all_letters()
    
    
    filename = "%s/%s" % (base_dir, "all_artists.json")
    logging.info("writing %d artists to %s"
                 % (len(all_artists), filename))

    with open(filename, "wb") as f:
        f.write(orjson.dumps(all_artists))
    """

    a_artists = fetch_letter('x')
    artists = [Artist(**a) for a in a_artists]

    pool = mp.Pool(100)

    logging.info("fetching artist ids")    
    out = pool.map(_get_ids, artists[:10])
    logging.info("done")

    logging.info("making s3 buckets for all letters")
    for letter in string.ascii_lowercase:
        s3_client.create_bucket("%s/%s" % (lyrics_root, letter))

    logging.info("fetching artst songs")
    with_songs = pool.map(_get_songs, out)
    logging.info("done")

    

    filename = "%s/%s" % (base_dir, "a_artist_songs.json")

    logging.info("writing %d artists to %s"
                 % (len(out), filename))

    
    with open(filename, "wb") as f:
        f.write(orjson.dumps(out))

    logging.info("done!")


if __name__ == "__main__":
    main()
