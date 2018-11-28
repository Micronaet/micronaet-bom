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
import excel_export

ExcelWriter = excel_export.excelwriter.ExcelWriter

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
# From config file:
cfg_file = os.path.expanduser('./openerp.cfg')

config = ConfigParser.ConfigParser()
config.read([cfg_file])
dbname = config.get('dbaccess', 'dbname')
user = config.get('dbaccess', 'user')
pwd = config.get('dbaccess', 'pwd')
server = config.get('dbaccess', 'server')
port = config.get('dbaccess', 'port')   # verify if it's necessary: getint

# ------------------    -----------------------------------------------------------
# Connect to ODOO:
# -----------------------------------------------------------------------------
odoo = erppeek.Client(
    'http://%s:%s' % (
        server, port), 
    db=dbname,
    user=user,
    password=pwd,
    )

# Pool used:
odoo.context = {
    'enable_bom_cost': True,
    'lang': 'it_IT',
    }

product_pool = odoo.model('product.product')
product_ids = product_pool.search([
    #('default_code', 'in', ('AN023', '005TX   AR')),
    #('default_code', '=ilike', 'BO2%'),
    ('mx_start_qty', '>', 0),
    ])

res = []
for product in product_pool.browse(product_ids):
    cost = product.bom_total_cost
    qty = product.mx_start_qty
    res.append((
        product.bom_cost_mode,
        product.inventory_category_id.name if product.inventory_category_id \
            else '',
        
        product.default_code,
        product.name,
        product.uom_id.name,
        
        qty,
        cost,
        product.bom_template_id,
        product.bom_total_cost_text,
        product.bom_total_cost_error,
        qty * cost,
        ))

# -----------------------------------------------------------------------------
#                            Excel file:
# -----------------------------------------------------------------------------
# Create WB:
workbooks = {
    'final': ExcelWriter('prodotti_finito.xlsx', verbose=True),
    'half': ExcelWriter('semilavorati.xlsx', verbose=True), 
    'material': ExcelWriter('materie_prime.xlsx', verbose=True), 
    }

Excel = ExcelWriter(xlsx_file, verbose=True)
pages = {
    'final': 0,
    'half': 0, 
    'material': 0, 
    }

#Excel.create_worksheet(page)
for page in pages:
    Excel.create_worksheet(page)
    Excel.column_width(page, (
        15,
        15, 
        30, 
        20,
        5,
        
        9,
        9,
        9,
        
        50,
        5,
        12,
        12,
        ))
        
# Create format:
f_title = Excel.get_format('title')
f_header = Excel.get_format('header')

f_text = Excel.get_format('text')
f_number = Excel.get_format('number')

f_text_red = Excel.get_format('bg_red')
f_number_red = Excel.get_format('bg_red_number')

for page in pages:
    Excel.write_xls_line(page, pages[page], (
        u'Categoria',
        u'Codice',
        u'Name',
        u'Modello ind.',
        u'UM',
        
        u'Q.',
        u'Costo',        
        u'Costo modello',    
            
        u'Dettaglio',
        u'Errore',
        u'Subtotale',
        u'Subtotale modello',
        ), f_header)
    pages[page] += 1    


for product in sorted(res):
    page = product[0]
    template = product[7]
    if template:
        template_name = template.default_code
        industrial = template.from_industrial
        subtotal_industrial = product[5] * industrial
    else:
        template_name = ''
        industrial = ''
        subtotal_industrial = ''

    if product[9]: # Error:
        text = f_text_red
        number = f_number_red
    else:
        text = f_text
        number = f_number
    Excel.write_xls_line(page, pages[page], (
        product[1], # Category
        product[2], # Code
        product[3], # Name
        template_name, # Template
        product[4], # UOM
        
        (product[5], number),
        (product[6], number),
        (industrial, number),
        
        product[8],
        'X' if product[9] else '',
        (product[10], number),
        (subtotal_industrial, number),        
        ), text)
    pages[page] += 1
del(Excel)
