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
file_excel = './controllo_distinte.xlsx'

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
line_pool = odoo.model('mrp.bom.line')

# -----------------------------------------------------------------------------
# Excel read:
# -----------------------------------------------------------------------------
assign_code = 'ASSEGNARE'
col_names = {
    'MT': ('[Materassino]', 29),
    'TL': ('[Telo]', 26),
    }
#bom_id = 11256 #DYNAMIC.2
bom_id = 7366 #DYNAMIC.1

try:
    wb = xlrd.open_workbook(file_excel)
except:
    print 'Errore reading file: %s' % file_excel
    sys.exit()

log_f = open('./regole.csv', 'w')
def write_log(log_f, message, verbose=True):
    ''' Write log on file and vider
    '''    
    if verbose:
        print message 
    log_f.write(message + '\n')
    return 
    
write_log(log_f, 'Nasc.|Ord.|Pagina|Riga|Prodotto|Componente|Note|Esito\n')
mask_log = open('./mask.csv', 'w')

for page in wb.sheet_names():
    if not page[:2] in col_names:
         #write_log(log_f, '\nJump page: %s' % page)
        continue 
    #write_log(log_f, '\nPage: %s' % page)
    sheet = wb.sheet_by_name(page)
    
    col_name, category_id = col_names[page[:2]]
    
    # -------------------------------------------------------------------------
    # Find column to check:    
    # -------------------------------------------------------------------------
    col_check = 0
    for col in range(5, sheet.ncols):
        if sheet.cell_value(1, col) == col_name:
            col_check = col
            break
    
    if not col_check:
        write_log(log_f, 'Cannot fine ref. colums  page: %s' % page)
        continue
                
    for row in range(2, sheet.nrows): # jump title, header row
        default_code = sheet.cell_value(row, 2).strip()      
        ordered = sheet.cell_value(row, 1).strip()      
        check_code = sheet.cell_value(row, col_check).strip()

        if default_code == page: 
            #write_log(
            #    log_f, '%s. OK (TEMPLATE): %s' % (row, default_code))
            continue # jump template line (no rule creation)
            
        correct_code = '%sS%s' % (
            default_code[:1],
            default_code[2:12].strip()
            )
            
        if check_code == correct_code: # Correct
            #write_log(
            #    log_f, '%s. OK: %s >> %s' % (
            #        row, default_code, correct_code))
            continue
        elif check_code != assign_code: # Wrong code create rule
            message = '|%s|%s|%s|%s|%s|ERRATO %s|' % (
                ordered, page, row, default_code, correct_code, check_code)
        else: # Placeholder
            message = '|%s|%s|%s|%s|%s|ASSEGNARE|' % (
                ordered, page, row, default_code, correct_code)

        # ---------------------------------------------------------------------
        # Find component:
        # ---------------------------------------------------------------------
        error = False
        # Product:
        product_ids = product_pool.search([
            ('default_code', '=', default_code)])
        if product_ids:
            product_id = product_ids[0]            
        else:
            message += 'ERR prodotto %s' % default_code
            error = True

        # Component:
        product_ids = product_pool.search([
            ('default_code', '=', correct_code)])
        if product_ids:
            correct_id = product_ids[0]            
        else:
            message += 'ERR componente %s' % correct_code
            error = True
        if not error:
            message += 'OK'

        write_log(log_f, message) 

        if error:
            continue

        # ---------------------------------------------------------------------
        # Rule creation:
        # ---------------------------------------------------------------------
        dynamic_mask = (default_code + '%').replace(' ', '_')
        line_ids = line_pool.search([
            ('bom_id', '=', bom_id),
            ('product_id', '=', correct_id),
            ('category_id', '=', category_id),
            ('dynamic_mask', '=', dynamic_mask),
            ])
        if line_ids:  
            mask_log.write('%s|%s|%s|%s|PRESENTE\n' % (
                correct_id,
                category_id,
                dynamic_mask,
                1,
                ))
        else:
            data = {
                'bom_id': bom_id,
                'product_id': correct_id,
                'category_id': category_id,
                'dynamic_mask': dynamic_mask,
                'product_qty': 1,
                #'product_uom':
                }
                
            mask_log.write('%s|%s|%s|%s|CREATA\n' % (
                correct_id,
                category_id,
                dynamic_mask,
                1,
                ))
            import pdb; pdb.set_trace()
            line_pool.create(data)            
