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
xlsx_file = './inventario.xlsx'

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
odoo.context = {'enable_bom_cost': True}

product_pool = odoo.model('product.product')
product_ids = product_pool.search([
    #('default_code', 'in', ('AN023', '005TX   AR')),
    #('default_code', '=ilike', '005%'),
    ('mx_start_qty', '>', 0),
    ])

res = []
for product in product_pool.browse(product_ids):
    cost = product.bom_total_cost
    qty = product.mx_start_qty
    res.append((
        product.bom_cost_mode,
        product.default_code,
        product.name,
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
Excel = ExcelWriter(xlsx_file, verbose=True)
pages = {
    'material': 0, 
    'half': 0, 
    'final': 0,
    }

#Excel.create_worksheet(page)
for page in pages:
    Excel.create_worksheet(page)
    Excel.column_width(page, (
        20,
        40, 
        20,
        
        10,
        10,
        10,
        
        50,
        5,
        10,
        10,
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
        u'Codice',
        u'Name',
        u'Modello ind.',
        
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
    template = product[5]
    if template:
        template_name = template.default_code
        industrial = template.from_industrial
        subtotal_industrial = product[3] * industrial
    else:
        template_name = ''
        industrial = ''
        subtotal_industrial = ''

    if product[7]: # Error:
        text = f_text_red
        number = t_number_red
    else
        text = f_text
        number = t_number
    Excel.write_xls_line(page, pages[page], (
        product[1],
        product[2],
        template_name,
        
        (product[3], number),
        (product[4], number),
        (industrial, number),
        
        product[6],
        'X' if product[7] else '',
        (product[8], number),
        (subtotal_industrial, number),        
        ), text)
    pages[page] += 1
del(Excel)
