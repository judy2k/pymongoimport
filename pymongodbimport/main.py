#!/usr/bin/env python
'''
Created on 19 Feb 2016

Need tests for skip larger than file size.

@author: jdrumgoole
'''
import argparse
import sys
import logging

from mongodb_utils.mongodb import MongoDB
from pymongodbimport.fileprocessor import FileProcessor 
from pymongodbimport.fieldconfig import FieldConfig
from pymongodbimport.argparser import pymongodb_arg_parser
from pymongodbimport.logger import Logger

def mainline_argsparsed( args ):
    '''
    Expects the output of parse_args.
    '''
    
    log = logging.getLogger( Logger.LOGGER_NAME )
    Logger.add_file_handler( Logger.LOGGER_NAME )
    
    log.info( "Started pymongodbimport")
    client = MongoDB( args.host).client()
    database = client[ args.database ]
    collection = database[ args.collection ]
        
        
    if args.genfieldfile :
        args.hasheader = True
        
    if args.drop :
        if args.restart :
            log.info( "Warning --restart overrides --drop ignoring drop commmand")
        else:
            database.drop_collection( args.collection )
            log.info( "dropped collection: %s.%s", args.database, args.collection )
         
    if args.genfieldfile :
        for i in args.filenames :
            fc_filename = FieldConfig.generate_field_file( i, args.delimiter )
            log.info( "Creating '%s' from '%s'", fc_filename, i )
        sys.exit( 0 )
    elif args.filenames:   
        log.info(  "Using database: %s, collection: %s", args.database, args.collection )
        log.info( "processing %i files", len( args.filenames ))
    
        if args.batchsize < 1 :
            log.warn( "Chunksize must be 1 or more. Chunksize : %i", args.batchsize )
            sys.exit( 1 )
        try :
            file_processor = FileProcessor( collection, args.delimiter, args.onerror, args.id, args.batchsize )
            file_processor.processFiles( args.filenames, args.hasheader, args.fieldfile, args.restart )
        except KeyboardInterrupt :
            log.warn( "exiting due to keyboard interrupt...")
    else:
        log.info( "No input files: Nothing to do") 

def mainline( args ):
    
    __VERSION__ = "1.4"
    
    '''
    Expect to recieve sys.argv or similar
    
    1.3 : Added lots of support for the NHS Public Data sets project. --addfilename and --addtimestamp.
    Also we now fail back to string when type conversions fail.
    
    >>> mainline( [ 'test_set_small.txt' ] )
    database: test, collection: test
    files ['test_set_small.txt']
    Processing : test_set_small.txt
    Completed processing : test_set_small.txt, (100 records)
    Processed test_set_small.txt
    '''
    
    usage_message = '''
    
    pymongodbimport is a python program that will import data into a mongodb
    database (default 'test' ) and a mongodb collection (default 'test' ).
    
    Each file in the input list must correspond to a fieldfile format that is
    common across all the files. The fieldfile is specified by the 
    --fieldfile parameter.
    
    An example run:
    
    python pymongodbimport.py --database demo --collection demo --fieldfile test_set_small.ff test_set_small.txt
    '''
    
    parser = argparse.ArgumentParser( parents = pymongodb_arg_parser(), usage=usage_message, version= __VERSION__)
    args= parser.parse_args( args )    
    mainline_argsparsed( args )
    
    
if __name__ == '__main__':
    
    mainline( sys.argv[1:] )