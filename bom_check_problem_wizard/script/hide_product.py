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

# Path of file
file_excel = './hide.xlsx'

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

# -----------------------------------------------------------------------------
# Excel read:
# -----------------------------------------------------------------------------
try:
    wb = xlrd.open_workbook(file_excel)
except:
    print 'Errore reading file: %s' % file_excel
    sys.exit()
sheet = wb.sheet_by_name('regole')
            
for row in range(1, sheet.nrows): # jump title, header row
    default_code = sheet.cell_value(row, 4).strip()      
    hide = sheet.cell_value(row, 0).strip().upper()
    if hide != 'X':
        continue # jump template line (no rule creation)

    product_ids = product_pool.search([
        ('default_code', '=', default_code),
        ])

    if product_ids:
        product_pool.write(product_ids, {
            'active': False,
            })            
        print 'Hide %s' % default_code
    else:
        print 'Cannot hide %s' % default_code

