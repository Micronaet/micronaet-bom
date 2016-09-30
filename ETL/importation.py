#!/usr/bin/env python
# -*- encoding: utf-8 -*-

# use: partner.py file_csv_to_import

# Modules required:
import xmlrpclib
import csv
import sys
import ConfigParser
import os

cfg_file = os.path.expanduser('~/etl/Access/import/openerp.cfg')

config = ConfigParser.ConfigParser()
config.read([cfg_file])
dbname = config.get('dbaccess', 'dbname')
user = config.get('dbaccess', 'user')
pwd = config.get('dbaccess', 'pwd')
server = config.get('dbaccess', 'server')
port = config.get('dbaccess', 'port')   # verify if it's necessary: getint
separator = config.get('dbaccess', 'separator') # test
verbose = eval(config.get('import_mode', 'verbose'))

header = 1 # non header on CSV file

sock = xmlrpclib.ServerProxy(
    'http://%s:%s/xmlrpc/common' % (server, port), allow_none=True)
uid = sock.login(dbname, user, pwd)
sock = xmlrpclib.ServerProxy(
    'http://%s:%s/xmlrpc/object' % (server, port), allow_none=True)

# -----------------------------------------------------------------------------
# IMPORT PIPES:
# -----------------------------------------------------------------------------
filename = os.path.expanduser('~/etl/Access/import/data/elenco_tubi.csv')
pipes = {}

lines = csv.reader(
    open(filename, 'rb'), 
    delimiter=separator,
    )
counter = -header
for line in lines:
    counter += 1 
    if counter <= 0:
       continue

    if not len(line): # jump empty lines
        continue
    
    ID = int(line[0])
    name = line[1]
    diameter = eval(line[2])
    thick = eval(line[3])
    resistence = line[4]
    length = eval(line[5])
    note = line[6]
    
    name = '%s Diam. %s Sp. %s L. %s' % (
        name,
        diameter,
        thick,
        length,
        )
        
    default_code = 'TBAL%sD%sS%s' % (
        length,
        diameter,
        thick,
        )
               
    item_ids = sock.execute(dbname, uid, pwd, 'product.product', 'search', [
           ('default_code', '=', default_code)])
    if item_ids:
        pipes[ID] = item_ids[0]
        sock.execute( # Search new code (if yet created)
            dbname, uid, pwd, 'product.product', 'write', item_ids, {
                'is_pipe': True,
                'name': name,
                'default_code': default_code,
                'uom_id': 1,
                'pipe_length':length,
                'pipe_diameter': diameter,
                'pipe_thick': thick, 
                })
    else:
        pipes[ID] = sock.execute( # Search new code (if yet created)
            dbname, uid, pwd, 'product.product', 'create', {
                'is_pipe': True,
                'name': name,
                'default_code': default_code,
                'uom_id': 1,
                'pipe_length':length,
                'pipe_diameter': diameter,
                'pipe_thick': thick, 
                })

print pipes
# -----------------------------------------------------------------------------
# READ PRODUCT USED:
# -----------------------------------------------------------------------------
filename = os.path.expanduser('~/etl/Access/import/data/elenco_articoli.csv')
product = {}

lines = csv.reader(
    open(filename, 'rb'), 
    delimiter=separator,
    )
counter = -header
for line in lines:
    counter += 1 
    if counter <= 0:
       continue

    if not len(line): # jump empty lines
        continue
    
    default_code = line[0]
    name = line[1]
               
    item_ids = sock.execute(dbname, uid, pwd, 'product.product', 'search', [
           ('default_code', '=', default_code)])
    if item_ids:
        product[default_code] = item_ids[0]        
        sock.execute( # Search new code (if yet created)
            dbname, uid, pwd, 'product.product', 'write', item_ids, {
                'name': name or 'Code %s' % default_code,
                'default_code': default_code,
                'uom_id': 1,
                })
    else:
        product[default_code] = sock.execute( # Search new code (if yet created)
            dbname, uid, pwd, 'product.product', 'create', {
                'name': name or 'Code %s' % default_code,
                'default_code': default_code,
                'uom_id': 1,
                })

print product
