"""
Created on 2 Mar 2016

@author: jdrumgoole
"""

from configparser import RawConfigParser
from datetime import datetime
import os
import csv
import logging
import textwrap
from dateutil.parser import parse

from pymongo_import.logger import Logger
from pymongo_import.config_file import Config_File
from pymongo_import.type_converter import Converter

from collections import OrderedDict
import re


class FieldConfigException(Exception):
    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)


class FieldConfig(object):
    '''
      Each field is represented by a section in the config parser
      For each field there are a set of configurations:
      
      type = the type of this field, int, float, str, date, 
      format = the way the content will be formatted for now really only used to date
      name = an optional name field. If not present the section name will be used.
      
      If the name field is "_id" then this will be used as the _id field in the collection.
      Only one name =_id can be present in any fieldConfig file.
      
      The values in this column must be unique in the source data file otherwise loading will fail
      with a duplicate key error.
      
    '''

    def __init__(self, cfgFilename, delimiter=",", hasheader=True, onerror="warn" ):
        '''
        Constructor
        '''
        self._logger = logging.getLogger(Logger.LOGGER_NAME)
        self._idField = None  # section on which name == _id
        # self._tags = ["name", "type", "format"]
        # self._cfg = RawConfigParser()
        # self._fieldDict = OrderedDict()
        self._doc_template = OrderedDict()
        self._delimiter = delimiter
        self._record_count = 0
        self._line_count = 0
        self._timestamp = None
        self._pid = os.getpid()
        self._onerror = onerror
        self._hasheader = hasheader
        self._config = None
        self._converter = Converter()
        if cfgFilename:
            self._config = Config_File(cfgFilename)

    def config(self):
        return self._config

    def hasheader(self):
        return self._hasheader

    def add_timestamp(self, timestamp):
        '''
        timestamp = "now" generate time once for all docs
        timestamp = "gen" generate a new timestamp for each doc
        timestamp = "none" don't add timestamp field
        '''
        self._timestamp = timestamp
        if timestamp == "now":
            self._doc_template["timestamp"] = datetime.utcnow()
        return self._doc_template

    def add_filename(self, filename):
        self._doc_template["filename"] = os.path.basename(filename)
        return self._doc_template

    def get_dict_reader(self, f):
        return csv.DictReader(f, fieldnames=self._config.fields(), delimiter=self._delimiter)

    def duplicateIDMsg(self, firstSection, secondSection):
        msg = textwrap.dedent("""\
        The type defintion '_id" occurs in more that one section (there can only be one
        _id definition). The first section is [%s] and the second section is [%s]
        """)

        return msg % (firstSection, secondSection)

    def delimiter(self):
        return self._delimiter


    @staticmethod
    def guess_type(s):
        '''
        Try and convert a string s to an object. Start with float, then try int
        and if that doesn't work return the string.
        '''

        if type(s) != type(""):
            raise ValueError("typeconvert expects a string parameter")

        v = None
        try:
            v = int(s)
            return (v, "int")
        except ValueError:
            pass

        try:
            v = float(s)
            return (v, "float")
        except ValueError:
            pass

        try:
            v = parse(s)  # dateutil.parse.parser
            return (v, "datetime")
        except ValueError:
            pass

        v = str(s)
        return (v, "str")

    def doc_template(self):
        return self._doc_template


    def type_convert(self, v, t):
        '''
        Use type entry for the field in the fieldConfig file (.ff) to determine what type
        conversion to use.
        '''
        v = v.strip()

        if t == "timestamp":
            v = datetime.datetime.fromtimestamp(int(v))
        elif t == "int":  # Ints can be floats
            try:
                # print( "converting : '%s' to int" % v )
                v = int(v)
            except ValueError:
                v = float(v)
        elif t == "float":
            v = float(v)
        elif t == "str":
            v = str(v)
        elif t == "datetime" or t == "date":
            if v == "NULL":
                v = None
            else:
                v = parse(v)
        else:
            raise ValueError

        return v

    def createDoc(self, doc, dictEntry):

        '''
        WIP
        Do we make gen id generate a compound key or another field instead of ID
        '''
        self._record_count = self._record_count + 1

        if self._timestamp == "gen":
            doc['timestamp'] = datetime.utcnow()

        # print( "dictEntry: %s" % dictEntry )
        fieldCount = 0
        for k in self._config.fields():
            # print( "field: %s" % k )
            # print( "value: %s" % dictEntry[ k ])
            fieldCount = fieldCount + 1

            if dictEntry[k] is None:
                if self._hasheader:
                    self._line_count = self._record_count + 1
                else:
                    self._line_count = self._record_count

                msg = "Value for field '{}' at line {} is 'None' which is not valid\n".format( k, self._line_count )
                #print(dictEntry)
                msg = msg + "\t\t\tline:{}:'{}'".format( self._record_count, self._delimiter.join( [ str(v) for v in dictEntry.values()]))
                if self._onerror == "fail" :
                    self._logger.error( msg)
                    raise ValueError(msg)
                elif self._onerror == "warn":
                    self._logger.warning(msg)
                    continue
                else:
                    continue

            if k.startswith("blank-") and self._onerror == "warn":  # ignore blank- columns
                self._logger.info("Field %i is blank [blank-] : ignoring", fieldCount)
                continue

            # try:
            try:
                type_field = self._config.type_value(k)
                if type_field in [ "date", "datetime"]:
                    format = self._config.format_value(k)
                    v = self._converter.convert_time(type_field, dictEntry[k], format)
                else:
                    v = self._converter.convert(type_field, dictEntry[k])

            except ValueError:

                if self._onerror == "fail":
                    self._logger.error("Error at line %i at field '%s'", self._record_count, k)
                    self._logger.error("type conversion error: Cannot convert '%s' to type %s", dictEntry[k],
                                       type_field)
                    raise
                elif self._onerror == "warn":
                    msg = "Parse failure at line {} at field '{}'".format( self._record_count, k )
                    msg = msg + " type conversion error: Cannot convert '{}' to type {} using string type instead".format(dictEntry[k], type_field)
                    v = str(dictEntry[k])
                elif self._onerror == "ignore":
                    v = str(dictEntry[k])
                else:
                    raise ValueError("Invalid value for onerror: %s" % self._onerror)

            if self._config.hasNewName(k):
                assert( self._config.name_value(k) != None)
                doc[self._config.name_value(k)] = v
            else:
                doc[k] = v

        #             except ValueError :
        #                 self._logger.error( "Value error parsing field : [%s]" , k )
        #                 self._logger.error( "read value is: '%s'", dictEntry[ k ] )
        #                 self._logger.error( "line: %i, '%s'", self._record_count, dictEntry )
        #                 #print( "ValueError parsing filed : %s with value : %s (type of field: $s) " % ( str(k), str(line[ k ]), str(fieldDict[ k]["type"])))
        #                 raise

        return doc

    @staticmethod
    def generate_field_filename(path, ext=".ff"):

        if not ext.startswith('.'):
            ext = "." + ext

        newpath = ""
        if re.match(r"^.*\.*\.[0-9]+$", path):
            pieces = path.split( ".")
            newpath = "{}{}".format( pieces[0], ext )
        else:
            newpath = os.path.splitext(path)[0] + ext

        return newpath

    @staticmethod
    def generate_field_file(path, delimiter=",", ext=".ff"):
        '''
        Take a file name and create a field file name and the corresponding field file data 
        from that file by reading the headers and 'sniffing' the first line of data.
        '''

        genfilename = FieldConfig.generate_field_filename(path, ext)

        with open(genfilename, "w") as genfile:
            # print( "The field file will be '%s'" % genfilename )
            with open(path, "r") as inputfile:
                header_line = inputfile.readline().rstrip().split(delimiter)  # strip newline
                value_line = inputfile.readline().rstrip().split(delimiter)
                if len(header_line) > len(value_line):
                    raise ValueError("Header line has more columns than value line: %i, %i" % (
                    len(header_line), len(value_line)))
            fieldCount = 0
            for i in header_line:

                if i == "":
                    i = "blank-%i" % fieldCount
                # print( i )

                i = i.strip()  # strip out white space
                if i.startswith('"'):
                    i = i.strip('"')
                if i.startswith("'"):
                    i = i.strip("'")
                i = i.replace('$', '_')  # not valid keys for mongodb
                i = i.replace('.', '_')  # not valid keys for mongodb
                (_, t) = FieldConfig.guess_type(value_line[fieldCount])
                fieldCount = fieldCount + 1
                genfile.write("[%s]\n" % i)
                genfile.write("type=%s\n" % t)

        return genfilename
