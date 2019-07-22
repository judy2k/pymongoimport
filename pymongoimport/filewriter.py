"""
Created on 23 Jul 2017

@author: jdrumgoole


"""
import time
from datetime import datetime, timedelta
import requests
import logging
import pymongo
from pymongo import errors

from pymongoimport.csvparser import CSVParser


def seconds_to_duration(seconds):
    delta = timedelta(seconds=seconds)
    d = datetime(1, 1, 1) + delta
    return "%02d:%02d:%02d:%02d" % (d.day - 1, d.hour, d.minute, d.second)


class FileWriter(object):

    def __init__(self, collection : pymongo.collection,
                 parser: CSVParser,
                 limit : int = 0):

        self._logger = logging.getLogger(__name__)
        self._collection = collection
        self._batch_size = 500
        self._totalWritten = 0

        self._parser = parser

        self._limit = limit

    def get_config(self):
        return self._config

    def get_batch_size(self):
        return self._batch_size

    def set_batch_size(self, size:int):
        if size < 1:
            raise ValueError("Invalid batchsize: {}".format(size))

        self._batch_size = size

    @staticmethod
    def skipLines(f, skip_count:int):
        """
        >>> f = open( "test_set_small.txt", "r" )
        >>> skipLines( f , 20 )
        20
        """

        line_count = 0
        if skip_count > 0:
            # print( "Skipping")
            dummy = f.readline()  # skicaount may be bigger than the number of lines i  the file
            while dummy:
                line_count = line_count + 1
                if line_count == skip_count:
                    break
                dummy = f.readline()
        return line_count

    def has_locator(self, collection, filename):

        result = collection.find_one({"locator": {"f": filename}})
        return result

    def add_locator(self, collection, doc, filename, record_number):

        if filename and record_number:
            doc['locator'] = {"f": filename, "n": record_number}
        elif filename:
            doc['locator'] = {"f": filename}
        elif record_number:
            doc['locator'] = {"n": record_number}

        return doc

    def download_file(url):
        """

        :return:
        """
        local_filename = url.split('/')[-1]
        # NOTE the stream=True parameter below
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:  # filter out keep-alive new chunks
                        f.write(chunk)
                        # f.flush()
        return local_filename

    def insert_file(self, filename, restart=False):

        start = time.time()
        total_written = 0
        results = None

        # with open( filename, "r", encoding = "ISO-8859-1") as f :

        # with open(filename, newline="") as f:

            # if self._parser.hasheader():
            #     self.skipLines(f, 1)  # skips header if present

            # reader = self._parser.get_dict_reader(f)

        doc_generator = self._parser.parse_file(filename, add_locator=True)


        time_start = time.time()
        inserted_this_quantum = 0
        total_read = 0
        insert_list = []

        try:
            for doc in doc_generator:
                # total_read = total_read + 1
                # if self._limit > 0:
                #     if total_read > self._limit:
                #         break
                # if len(dictEntry) == 1:
                #     if self._logger:
                #         self._logger.warning("Warning: only one field in "
                #                              "input line. Do you have the "
                #                              "right delimiter set ? "
                #                              "( current delimiter is : '%s')",
                #                              self._config.delimiter())
                #         self._logger.warning("input line : '%s'", "".join(dictEntry.values()))
                #
                # d = self._parser.parse_line(dictEntry)
                #
                # d = self.add_locator(self._collection, d, filename, total_read)

                insert_list.append(doc)
                if total_read % self._batch_size == 0:
                    results = self._collection.insert_many(insert_list)
                    total_written = total_written + len(results.inserted_ids)
                    inserted_this_quantum = inserted_this_quantum + len(results.inserted_ids)
                    insert_list = []
                    time_now = time.time()
                    elapsed = time_now - time_start
                    docs_per_second = self._batch_size / elapsed
                    time_start = time_now
                    if self._logger:
                        self._logger.info(
                            "Input:'{}': docs per sec:{:7.0f}, total docs:{:>10}".format(filename, docs_per_second,
                                                                                         total_written))

        except UnicodeDecodeError as exp:
            if self._logger:
                self._logger.error(exp)
                self._logger.error("Error on line:%i", total_read + 1)
            raise;

        if len(insert_list) > 0:
            # print(insert_list)
            try:
                results = self._collection.insert_many(insert_list)
                total_written = total_written + len(results.inserted_ids)
                insert_list = []
                if self._logger:
                    self._logger.info("Input: '%s' : Inserted %i records", filename, total_written)
            except errors.BulkWriteError as e:
                self._logger.error(f"pymongo.errors.BulkWriteError: {e.details}")

        finish = time.time()
        if self._logger:
            self._logger.info("Total elapsed time to upload '%s' : %s", filename, seconds_to_duration(finish - start))
        return total_written
