#!/usr/bin/env python
# -*- encoding: utf-8 -*-

# use: partner.py file_csv_to_import

# Modules required:
import xmlrpclib
import csv
import sys
import ConfigParser
import os

folder = sys.argv[1]
path = os.path.expanduser(os.path.join(
    '~/etl/Access/import/data',
    folder,
    ))
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
#                          IMPORT PIPES:
# -----------------------------------------------------------------------------
filename = os.path.join(path, 'elenco_tubi.csv')
pipes = {}

lines = csv.reader(
    open(filename, 'rb'), 
    delimiter=separator,
    )
i = -header
for line in lines:
    i += 1 
    if i <= 0:
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
    if len(line) == 8:
        weight = float(line[7] or '0')
    else:
        weight = 0.0
    
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
               
    data = {
        'is_pipe': True,
        'name': name,
        'default_code': default_code,
        'uom_id': 1,
        'pipe_length':length,
        'pipe_diameter': diameter,
        'pipe_thick': thick, 
        'pipe_resistence': resistence,
        'weight': weight, # only Fe
        }           
    item_ids = sock.execute(dbname, uid, pwd, 'product.product', 'search', [
           ('default_code', '=', default_code)])
    if item_ids:
        pipes[ID] = item_ids[0]
        sock.execute( # Search new code (if yet created)
            dbname, uid, pwd, 'product.product', 'write', item_ids, data)
    else:
        pipes[ID] = sock.execute( # Search new code (if yet created)
            dbname, uid, pwd, 'product.product', 'create', data)

print 'Pipes:', pipes
print filename, 'row:', i

# -----------------------------------------------------------------------------
#                        READ PRODUCT USED (PARENT):
# -----------------------------------------------------------------------------
filename = os.path.join(path, 'elenco_articoli.csv')
products = {}
parents = {}

lines = csv.reader(
    open(filename, 'r'), 
    delimiter=separator,
    )
i = -header
for line in lines:
    i += 1 
    if i <= 0:
       continue

    if not len(line): # jump empty lines
        continue
    
    default_code = line[0]
    name = line[1]

    # -------------------------------------------------------------------------
    # Manage product:                
    # -------------------------------------------------------------------------
    data = {
        'name': name or 'Code %s' % default_code,
        'default_code': default_code,
        'uom_id': 1,
        }
    item_ids = sock.execute(dbname, uid, pwd, 'product.product', 'search', [
           ('default_code', '=', default_code)])
    if item_ids:
        products[default_code] = item_ids[0]        
        sock.execute( # Search new code (if yet created)
            dbname, uid, pwd, 'product.product', 'write', item_ids, data)
    else:
        products[default_code] = sock.execute( # Search new code (if yet created)
            dbname, uid, pwd, 'product.product', 'create', data)

    # -------------------------------------------------------------------------
    # Manage BOM:
    # -------------------------------------------------------------------------
    # Read template:        
    product_id = products[default_code]
    template = sock.execute( 
        dbname, uid, pwd, 'product.product', 'read', product_id, 
        ('product_tmpl_id', ))
    product_tmpl_id = template['product_tmpl_id'][0]
    
    if default_code not in parents:
        data = {
            'code': default_code,
            'product_tmpl_id': product_tmpl_id,
            'product_id': product_id,
            'product_qty': 1, 
            'product_uom': 1,
            'code': default_code,
            'bom_category': 'half',
            'bom_line_ids': [(5, False, False)], # reset bon lines (first time)
            }

        parent_ids = sock.execute(dbname, uid, pwd, 'mrp.bom', 'search', [
            ('product_id', '=', product_id), # TODO template?
            ])
            
        if parent_ids:
            parents[default_code] = parent_ids[0]        
            sock.execute(
                dbname, uid, pwd, 'mrp.bom', 'write', parent_ids, data)
        else:
            parents[default_code] = sock.execute(
                dbname, uid, pwd, 'mrp.bom', 'create', data)

print 'Products:', products
print 'Parents:', parents

print filename, 'row:', i

# -----------------------------------------------------------------------------
#                                 SET MIN ORDER:
# -----------------------------------------------------------------------------
if folder == 'alluminio':
    filename = os.path.join(path, 'multipli_ordine.csv')

    lines = csv.reader(
        open(filename, 'rb'),
        delimiter=separator,
        )
    i = -header
    for line in lines:
        i += 1 
        if i <= 0:
           continue

        if not len(line): # jump empty lines
            continue
        
        description = line[0] # not used
        pipe_min_order = int(line[1])
        diameter = line[3]
                   
        item_ids = sock.execute(
            dbname, uid, pwd, 'product.product', 'search', [
                ('is_pipe', '=', True),
                ('pipe_diameter', '=', diameter),
                ])
            
        if item_ids:
            sock.execute( # Search new code (if yet created)
                dbname, uid, pwd, 'product.product', 'write', item_ids, {
                    'pipe_min_order': pipe_min_order,
                    })

    print filename, 'row:', i
# -----------------------------------------------------------------------------
#                                BOM DETAILS:
# -----------------------------------------------------------------------------
filename = os.path.join(path, 'dettagli_componenti.csv')
boms = {}
lines = csv.reader(
    open(filename, 'r'),
    delimiter=separator,
    )

i = -header
for line in lines:
    i += 1 
    if i <= 0:
       continue

    if not len(line): # jump empty lines
        continue

    component_code = line[0].upper()
    description = line[1] 
    default_code = line[2]
    try:
        length_cut = eval(line[3])
    except:
        print i, 'Length error or 0, jump'
        continue    
    #waste_cut = eval(line[3])
    try:
        pipe_id = int(line[4])
    except:
        print i, 'Pipe ID error or not present, jump'
        continue
        
    part_x_pipe = eval(line[5])
    total = int(line[6])

    name = '%s %s per %s' % (description, component_code, default_code)
    
    # -------------------------------------------------------------------------
    #                         Component part:
    # -------------------------------------------------------------------------
    component_ids = sock.execute(
        dbname, uid, pwd, 'product.product', 'search', [
            ('default_code', '=', component_code),
            ])
        
    data = {
        'default_code': component_code,
        'name': name,
        'uom_id': 1,                
        }    
    if component_ids:
        products[component_code] = component_ids[0]        
        sock.execute( # Search new code (if yet created)
            dbname, uid, pwd, 'product.product', 'write', component_ids, data)
    else:
        products[component_code] = sock.execute( 
            dbname, uid, pwd, 'product.product', 'create', data)
            
    # Read template:        
    component_id = products[component_code]
    template = sock.execute( 
        dbname, uid, pwd, 'product.product', 'read', component_id, 
        ('product_tmpl_id', ))
    product_tmpl_id = template['product_tmpl_id'][0]

    # -------------------------------------------------------------------------
    # Add component in parent bom:
    # -------------------------------------------------------------------------
    if default_code not in parents:
        print i, 'Code not in parent bom', default_code
        continue
        
    parent_id = parents[default_code] 
   
    product_qty = total # 1 # XXX
    data = {
        'bom_id': parent_id,
        'product_id': component_id,
        'type': 'normal',
        'product_qty': product_qty,
                
        'product_uom': 1,
        'product_rounding': 1,
        'product_efficiency': 1,        
        }

    sock.execute(dbname, uid, pwd, 'mrp.bom.line', 'create', data)
              
    # -------------------------------------------------------------------------
    #                        BOM for component (HEADER):
    # -------------------------------------------------------------------------
    component_id = products[component_code]
    if component_id not in boms:
        data = {
            'code': component_code,
            'product_tmpl_id': product_tmpl_id,
            'product_id': products[component_code],
            'product_qty': 1, 
            'product_uom': 1,
            'code': component_code,
            'bom_category': 'half',
            'bom_line_ids': [(5, False, False)], # reset bon lines (first time)
            }

        bom_ids = sock.execute(dbname, uid, pwd, 'mrp.bom', 'search', [
            ('product_id', '=', component_id), # TODO template?
            ])
            
        if bom_ids:
            boms[component_id] = bom_ids[0]       
            sock.execute(
                dbname, uid, pwd, 'mrp.bom', 'write', bom_ids, data)
        else:
            boms[component_id] = sock.execute(
                dbname, uid, pwd, 'mrp.bom', 'create', data)
                
    # -------------------------------------------------------------------------
    #                           BOM line add:
    # -------------------------------------------------------------------------
    bom_id = boms[component_id] 
    if pipe_id not in pipes:
        print i, 'Pipe %s not found' % pipe_id
        continue
    if not part_x_pipe:
        print i, 'Part per pipe is 0'
        continue
       
    product_qty = 1.0 / part_x_pipe # total * 1.0 / part_x_pipe # XXX
    data = {
        'bom_id': bom_id,
        'product_id': pipes[pipe_id],
        'type': 'normal',
        'product_qty': product_qty,
                
        'length_cut': length_cut,
        # waste_cut
        'part_x_pipe': part_x_pipe,
        'pipe_total': 1.0, # total, # XXX remove
        
        'product_uom': 1,
        'product_rounding': 1,
        'product_efficiency': 1,        
        }
    try:
        boms[component_id] = sock.execute(
            dbname, uid, pwd, 'mrp.bom.line', 'create', data)
    except:
        print i, 'Create bom line with data not correct', data
        continue
        
print filename, 'row:', i      
