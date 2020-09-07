import os
import re
import string
import requests
import functools
import logging
import time
import warnings

from selenium import webdriver
from bs4.element import Tag
from bs4 import BeautifulSoup

class Artist():
    def __init__(self, name, url):
        self.name = name
        self.url = url

def get_with_phantom(url, attempt=0, attempts=5):
    driv

def get_and_scroll(url,
                   attempt=0,
                   attempts=5,
                   implicit_wait=30,
                   scroll_pause_time=3.5):
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
            return fetch_with_retries(url, attempt+1)
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
        letters=string.ascii_lowercase):

    artist_list = functools.reduce(
        lambda acc, letter: acc + fetch_letter(letter, base_url),
        letters,
        [])

    return artist_list

def fetch_letter(
        letter,
        base_url="https://genius.com/artists-index/%s/all?page=%d",
        max_page=1000):

    pages = []
    for page in range(max_page):
        logging.debug("letter: %s, page: %d" % (letter, page))
        new_pages = fetch_letter_page(letter, page+1, base_url)

        if len(new_pages):
            logging.info("got up to page %d for letter %s" %
                         (letter, page))
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
            "name": li.text.strip().encode('utf-8')
        } for li in 
        soup.find('ul', {'class': "artists_index_list"})
        if type(li) is Tag and li.find(li)]

def fetch_all_artists(
        base_url="https://genius.com/artists-index/%s/all?page=%d",
        letters=string.ascii_lowercase):
    
    artists_data = fetch_all_letters(base_url, letters)
    return [Artist(**artist) for artist in artists_data]

def fetch_all():
    """
    
    """
    pass
