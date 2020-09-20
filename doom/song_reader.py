import logging
import gzip
import orjson
import functools
import pickle

import numpy as np
import keras.utils as ku 
import multiprocessing as mp

from keras.preprocessing.text import Tokenizer
from keras.preprocessing.sequence import pad_sequences

from .utils import logger_init, worker_init

"""
various utilities for reading a unified artists & song
data for subsequent modeling
"""

def read_file(path):
    """
    a generator for processing line-delimited json
    one line at a time
    """
    logging.info("opening %s" % path)
    with gzip.open(path, 'rb') as f:
        for line in f:
            yield orjson.loads(line)

def song_to_lines(song):
    """
    takes a song and returns an array where
    each line is an element
    """
    if 'lyrics' in song and song['lyrics']:
        return song['lyrics'].lower().split("\n")
    else:
        return []

def artist_to_lines(artist):
    """
    turns an artist into a list of song lines
    todo: make this a parallel process?
          thinking no for now since most artists
          have a small number of songs
    """
    logging.debug("reading songs for %s" % artist['name'])
    if 'songs' in artist and artist['songs']:
        return functools.reduce(
            lambda acc, x: acc + song_to_lines(x),
            artist['songs'],
            []
        )
    else:
        return []

def artist_file_to_lines(path,
                         pool=mp.Pool(mp.cpu_count())):
    """
    turns a collection of artist data into a list of song
    lines.
    """
    return functools.reduce(
        lambda acc, x: acc + x,
        pool.map(artist_to_lines, read_file(path)),
        []
    )

def read_songs(path):
    """
    reads song data from a pickle file
    """
    return pickle.load(
        open(path, "rb" )
    )

def write_songs(song_data, path):
    """
    write song data to a pickle file
    """
    pickle.dump(
        song_data,
        open(path, "wb")
    )

def dataset_preparation(corpus, tokenizer=Tokenizer()):
    """
    corpus are the lines in a song
    """
    tokenizer.fit_on_texts(corpus)
    total_words = len(tokenizer.word_index) + 1 
    
    input_sequences = []
    for line in corpus:
        token_list = tokenizer.texts_to_sequences([line])[0]
        
        for i in range(1, len(token_list)):
            n_gram_sequence = token_list[:i+1]
            input_sequences.append(n_gram_sequence)
    
    max_sequence_len = max([len(x) for x in input_sequences])
    input_sequences = np.array(
        pad_sequences(input_sequences,   
                      maxlen=max_sequence_len, padding='pre')
    )
    
    
    predictors, label = input_sequences[:,:-1], input_sequences[:,-1]
    label = ku.to_categorical(label, num_classes=total_words)
    
    return predictors, label, max_sequence_len, total_words
