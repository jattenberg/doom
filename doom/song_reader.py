import logging
import gzip
import orjson
import functools
import itertools
import pickle
import cld3
import re

import numpy as np
import keras.utils as ku 
import multiprocessing as mp

from tqdm import tqdm 
from optparse import OptionParser
from keras.preprocessing.text import Tokenizer
from keras.preprocessing.sequence import pad_sequences
from sklearn.feature_extraction.text import HashingVectorizer

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

def song_to_lines(song,
                  min_lines=20,
                  acceptable_languages=['en']):
    """
    takes a song and returns an array where
    each line is an element
    """
    if 'lyrics' in song and song['lyrics']:
        lines = song['lyrics'].lower().split("\n")
        if len(lines) >= min_lines:
            lang_prediction = cld3.get_language(
                song['lyrics']
            )
            if lang_prediction.is_reliable\
               and lang_prediction.language in acceptable_languages:
                return lines
            else:
                return []
        else:
            return []
    else:
        return []

def artist_to_lines(artist,
                    min_songs=10):
    """
    turns an artist into a list of song lines
    todo: make this a parallel process?
          thinking no for now since most artists
          have a small number of songs
    """
    logging.debug("reading songs for %s (%s)" %
                  (artist['name'], artist['artist_id']))
    if 'songs' in artist and artist['songs']:
        if len(artist['songs']) >= min_songs:
            return itertools.chain.from_iterable(
                map(song_to_lines, artist['songs'])
            )
        else:
            return []
    else:
        return []

def unique_artist_filter(artists):
    seen = set()
    for artist in artists:
        if artist['artist_id'] not in seen:
            seen.add(artist['artist_id'])
            yield artist

def artist_file_to_lines(path, pool):
    """
    turns a collection of artist data into a list of song
    lines.
    """
    
    return itertools.chain.from_iterable(
        tqdm(
            pool.imap_unordered(
                artist_to_lines,
                unique_artist_filter(
                    read_file(path)
                )
            )
        )
    )

def read_songs(path):
    """
    reads song data from a pickle file
    """
    return pickle.load(
        gzip.open(path, "rb" )
    )

def write_songs(song_data, path):
    """
    write song data to a pickle file
    """
    pickle.dump(
        song_data,
        gzip.open(path, "wb")
    )

def dataset_preparation(corpus, tokenizer=Tokenizer()):
    """
    corpus are the lines in a song

    builds dataset necessary for next word prediction tasks,
    including fitting the tokenizer and creating necessary
    statistics: max sequence length and total word count
    """
    tokenizer.fit_on_texts(corpus)
    total_words = len(tokenizer.word_index) + 1 
    
    input_sequences = []
    for line in tqdm(corpus):
        token_list = tokenizer.texts_to_sequences([line])[0]
        
        for i in range(1, len(token_list)):
            n_gram_sequence = token_list[:i+1]
            input_sequences.append(n_gram_sequence)
    
    max_sequence_len = max([len(x) for x in input_sequences])

    input_sequences = np.array(
        pad_sequences(
            input_sequences,   
            maxlen=max_sequence_len,
            padding='pre'
        )
    )
    
    predictors, label = input_sequences[:,:-1], input_sequences[:,-1]
    label = ku.to_categorical(label, num_classes=total_words)
    
    return predictors, label, max_sequence_len, total_words, tokenizer

def basic_splitter(line):
    return re.split(r'\s+', line)

def hash_to_sequence(line,
                     splitter=basic_splitter,
                     tokenizer=HashingVectorizer(n_features=2**16,
                                                 decode_error='ignore',
                                                 strip_accents='unicode')):
    tokens = splitter(line)
    return tokenizer.transform(tokens).nonzero()[1].tolist() # columns

def document_statistics(token_sequence):

    def accum_stats(stats, tokens):

        length = len(tokens) if tokens else 0
        largest = max(tokens) if tokens else 0

        return (max(length, stats[0]), max(largest, stats[1]))

    return functools.reduce(
        accum_stats,
        corpus,
        (0, 0)
    )

def line_to_features(line,
                     max_sequence_len,
                     total_words,
                     splitter=basic_splitter,
                     tokenizer=HashingVectorizer(n_features=2**16,
                                                 decode_error='ignore',
                                                 strip_accents='unicode')):
    token_list = hash_to_sequence(line,
                                  splitter,
                                  tokenizer)

    if token_list:
        input_sequences = [token_list[:i+1] for i in range(1, len(token_list))]
        for seq in np.array(
                pad_sequences(
                    input_sequences,
                    maxlen=max_sequence_length,
                    padding='pre')):
            yield (seq[:-1],
                   ku.to_categorical(seq[-1],
                                     num_classes=total_words))

def get_optparser():
    parser = OptionParser(
        usage="gather line-delimited gzipped json data and gather lyric lines"
    )

    parser.add_option("-i",
                      "--input",
                      action="store",
                      dest="input",
                      default="all_lyrics.json.gz",
                      help="location of the artist data to read")

    parser.add_option("-o",
                      "--output",
                      action="store",
                      dest="output",
                      default="lyrics.pkl",
                      help="location to store pickled lyric lines")

    parser.add_option("-L",
                      "--log_level",
                      action="store",
                      dest="log_level",
                      default="INFO",
                      help="log level to use")

    parser.add_option("-p",
                      "--pool",
                      action="store",
                      dest="pool",
                      default=mp.cpu_count(),
                      help="size of pool of workers for parallel execution")

    return parser

def main():
    opt_parser = get_optparser()
    (options, args) = opt_parser.parse_args()

    q_listener, q = logger_init(options.log_level.upper())

    pool = mp.Pool(int(options.pool),
                   worker_init,
                   [q])

    logging.info("reading songs from %s" % options.input)

    path = options.input
    splitter = basic_splitter
    tokenizer = HashingVectorizer(n_features=2**16,
                                  decode_error='ignore',
                                  strip_accents='unicode')
    seqs = [hash_to_sequence(line,
                             splitter,
                             tokenizer)\
            for line in artist_file_to_lines(path, pool)]

    max_seq_len, total_words = document_statistics(seqs)

    logging.info("got %d total words, longest seq is %d" %
                 (total_words, max_seq_len))


    output = {
        "seqs": seqs,
        "max_seq_len": max_seq_len,
        "total_words": total_words
    }

    logging.info("writing %d lines to %s" % (len(output), options.output))
    write_songs(output, options.output)

if __name__ == "__main__":
    main()
