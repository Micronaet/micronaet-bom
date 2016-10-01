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

# -----------------------------------------------------------------------------
# SET MIN ORDER:
# -----------------------------------------------------------------------------
filename = os.path.expanduser('~/etl/Access/import/data/multipli_ordine.csv')
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
    
    description = line[0] # not used
    pipe_min_order = int(line[1])
    diameter = line[3]
               
    item_ids = sock.execute(dbname, uid, pwd, 'product.product', 'search', [
        ('is_pipe', '=', True),
        ('pipe_diameter', '=', diameter),
        ])
        
    if item_ids:
        product[default_code] = item_ids[0]        
        sock.execute( # Search new code (if yet created)
            dbname, uid, pwd, 'product.product', 'write', item_ids, {
                'pipe_min_order': pipe_min_order,
                })

# -----------------------------------------------------------------------------
# DETAILS:
# -----------------------------------------------------------------------------
filename = os.path.expanduser('~/etl/Access/import/dati/dettagli_componenti.csv')
boms = {}
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

    component_code = line[0].upper()
    description = line[1] 
    product_code = line[2]
    cut_dimension = eval(line[3])
    pipe_id = line[4]
    cut = eval(line[5])
    total = line[6]    
    
    # -------------
    # Product part:
    # -------------
    item_ids = sock.execute(dbname, uid, pwd, 'product.product', 'search', [
        ('default_code', '=', component_code),
        ])
        
    if item_ids:
        product[component_code] = item_ids[0]        
        sock.execute( # Search new code (if yet created)
            dbname, uid, pwd, 'product.product', 'write', item_ids, {
                'default_code': default_code,
                })
    else:
        sock.execute( 
            dbname, uid, pwd, 'product.product', 'create', {
                'default_code': default_code,
                'name': '%s per %s' % (description, product_code),
                'uid_id': 1,                
                })

    # -------------
    # Product part:
    # -------------
    product_id = product[component_code]
    if product_id not in boms:
        bom_ids = sock.execute(dbname, uid, pwd, 'mrp.bom', 'search', [
            ('product_id', '=', product_id),
            # for template?
            ])
        if bom_ids:
            boms[product_id] = bom_ids        
        else:
            boms[product_id] = sock.execute(
                dbname, uid, pwd, 'mrp.bom', 'create', {
                    'default_code': default_code,
                    'product_id': product[component_code],
                    'product_qty': 1, 
                    'product_uom': 1,
                    'code': component_code,
                    })
                    
    # Search also in bom lines                    
      
