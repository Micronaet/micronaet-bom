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
import ConfigParser
import xlrd

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
cfg_file = os.path.expanduser('../openerp.cfg')

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
    'http://%s:%s' % (
        server, port), 
    db=dbname,
    user=user,
    password=pwd,
    )

product_pool = odoo.model('product.product')
# dynamic_bom_checked

# -----------------------------------------------------------------------------
# Excel read:
# -----------------------------------------------------------------------------

# Path of file
file_excel = './controllo settimanale.xlsx'

#Open document
try:
    wb = xlrd.open_workbook(file_excel)
except:
    print 'Errore reading file: %s' % file_excel
    sys.exit()

log_f = open('./update.log', 'w')

sheet = wb.sheet_by_name('Prodotti')
for row in range(2, sheet.nrows): # jump title, header row
    dynamic_bom_checked = sheet.cell_value(row, 3)
    default_code = sheet.cell_value(row, 0)        
    if dynamic_bom_checked.upper() != 'X':
        message = '%s. NOT UPDATE Code: %s\n' % (
            row, default_code
            )
        print message 
        log_f.write(message)    
        continue
    
    product_ids = product_pool.search([
        ('default_code', '=', default_code)])
    if product_ids:
        product_pool.write(product_ids, {
            'dynamic_bom_checked': True, 
            })
        message = '%s. UPDATED Code: %s\n' % (
            row, default_code,
            )
        print message 
        log_f.write(message)    
            
    else:
        message = '%s. PRODUCT NOT FOUND Code: %s\n' % (
            row, default_code,
            )
        print message 
        log_f.write(message)    
    
