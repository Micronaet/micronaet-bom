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
rename = []
for root, folders, files in os.walk('./controllare'):
    for f in files:
        
        if not f.endswith('xlsx'):   
            print 'Jump file: %s' % f
            continue
        
        # Path of file
        file_excel = os.path.join(root, f)
        file_history = os.path.join('.', 'controllare', 'history', f)
        print 'Load file: %s' % file_excel
        

        #Open document
        try:
            wb = xlrd.open_workbook(file_excel)
        except:
            print 'Errore reading file: %s' % file_excel
            sys.exit()

        log_f = open('./update.log', 'w')
        for name in wb.sheet_names():
            if name != 'Prodotti':
                print 'Jump sheet: %s' % name
                continue
            sheet = wb.sheet_by_name(name)
            for row in range(2, sheet.nrows): # jump title, header row
                try:
                    default_code = sheet.cell_value(row, 0)        
                except:
                    message = '%s. Column error: %s\n' % (row, name)
                    #print message 
                    #log_f.write(message)    
                    continue
                dynamic_bom_checked = sheet.cell_value(row, 3)
                        
                if dynamic_bom_checked.upper() != 'X':
                    message = '%s. NOT UPDATE Sheet: %s, Code: %s\n' % (
                        row, name, default_code
                        )
                    #print message 
                    #log_f.write(message)    
                    continue
                
                product_ids = product_pool.search([
                    ('default_code', '=', default_code)])
                if product_ids:
                    product_pool.write(product_ids, {
                        'dynamic_bom_checked': True, 
                        })
                    message = '%s. UPDATED Sheet: %s, Code: %s\n' % (
                        row, name, default_code,
                        )
                    print message 
                    log_f.write(message)    
                        
                else:
                    message = '%s. PRODUCT NOT FOUND Sheet: %s, Code: %s\n' % (
                        row, name, default_code,
                        )
                    print message 
                    log_f.write(message)   
                     
        rename.append((file_excel, file_history))
    break # only first folder            

for from_file, to_file in rename:
    print 'History %s > %s' % (from_file, to_file)
    os.rename(from_file, to_file)

