# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP) 
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
# Developer: Nicola Riolini @thebrush (<https://it.linkedin.com/in/thebrush>)
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. 
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import os
import sys
import erppeek
import xlrd
import ConfigParser


# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
# From config file:
cfg_file = os.path.expanduser('openerp.cfg')

config = ConfigParser.ConfigParser()
config.read([cfg_file])
dbname = config.get('dbaccess', 'dbname')
user = config.get('dbaccess', 'user')
pwd = config.get('dbaccess', 'pwd')
server = config.get('dbaccess', 'server')
port = config.get('dbaccess', 'port')   # verify if it's necessary: getint

# -----------------------------------------------------------------------------
# Connect to ODOO:
# -----------------------------------------------------------------------------
odoo = erppeek.Client(
    'http://%s:%s' % (server, port), 
    db=dbname, user=user, password=pwd,
    )
    
# Pool used:
bom_line_pool = odoo.model('mrp.bom.line') 

mask = '\_30%'

line_ids = bom_line_pool.search([
    ('dynamic_mask', 'ilike', mask),
    ])
for line in bom_line_pool.browse(line_ids):
    mask = line.dynamic_mask
    mask0 = '0' + mask[1:]
    mask1 = '1' + mask[1:]
    print '\nFrom %s to %s and %s' % (mask, mask0, mask1)
    
    # Create new rule:
    data = {
        #'product_uos_qty': line.,
        #'date_stop': line.,
        'product_uom': line.product_uom.id,
        'sequence': line.sequence,
        'date_start': line.date_start,
        #'routing_id': line.,
        'product_rounding': line.product_rounding,
        'product_qty': line.product_qty,
        #'product_uos': line.product_uos,
        'product_efficiency': line.product_efficiency,
        'type': line.type,
        'bom_id': line.bom_id.id,
        'product_id': line.product_id.id,
        'obsolete': line.obsolete,
        'note': line.note,
        'category_id': line.category_id.id,
        'dynamic_mask': mask0,
        #'halfwork_id': line.halfwork_id,
        #old_cost
        #migration_old_id
        #sql_import
        #length_cut
        #waste_cut
        #pipe_total
        #part_x_pipe
        }
    print ' Create: %s' % (data, )
    bom_line_pool.create(data)  
    
    # Update previous rule:
    data = {
        'dynamic_mask': mask1,        
        }
    print 'Update %s: %s' % (line.id, data, )    
    bom_line_pool.write([line.id], data) 
    import pdb; pdb.set_trace()
    
    

    
    



