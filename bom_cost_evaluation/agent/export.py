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
    #('default_code', '=ilike', '005TX%'),
    #('inventory_category_id', '=', False),
    ('mx_start_qty', '>', 0),
    ])

not_product_ids = product_pool.search([
    ('mx_start_qty', '<=', 0),
    ])

res = []
for product in product_pool.browse(product_ids):
    cost = product.bom_total_cost
    qty = product.mx_start_qty
    if product.inventory_category_id:
        category = product.inventory_category_id.name
    else:
        category = 'NON CATALOGATO'     
    res.append((
        product.bom_cost_mode,
        category,
        
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
    'final': ExcelWriter('./prodotti_finito.xlsx', verbose=True),
    'half': ExcelWriter('./semilavorati.xlsx', verbose=True), 
    'material': ExcelWriter('./materie_prime.xlsx', verbose=True), 
    }

excel_format = {
    'final': {
        'f_title': workbooks['final'].get_format('title'),
        'f_header': workbooks['final'].get_format('header'),
        'f_text': workbooks['final'].get_format('text'),
        'f_number': workbooks['final'].get_format('number'),
        'f_text_red': workbooks['final'].get_format('bg_red'),
        'f_number_red': workbooks['final'].get_format('bg_red_number'),
        },
    'half': {
        'f_title': workbooks['half'].get_format('title'),
        'f_header': workbooks['half'].get_format('header'),
        'f_text': workbooks['half'].get_format('text'),
        'f_number': workbooks['half'].get_format('number'),
        'f_text_red': workbooks['half'].get_format('bg_red'),
        'f_number_red': workbooks['half'].get_format('bg_red_number'),
        },
    'material': {
        'f_title': workbooks['material'].get_format('title'),
        'f_header': workbooks['material'].get_format('header'),
        'f_text': workbooks['material'].get_format('text'),
        'f_number': workbooks['material'].get_format('number'),
        'f_text_red': workbooks['material'].get_format('bg_red'),
        'f_number_red': workbooks['material'].get_format('bg_red_number'),
        },
    }
    
# Counters:
counters = {
    'final': {},
    'half': {}, 
    'material': {},     
    }

totals = {
    'final': {},
    'half': {}, 
    'material': {},     
    }

# -----------------------------------------------------------------------------
# Utility:
# -----------------------------------------------------------------------------
def get_page(wb_name, ws_name, counters, excel_format):
    ''' Get WS page or create if not present 
        Add also header
        wb_name: Name of workbook (3 mode: final, half, material)
        ws_name: Sheet description
        counters: counter for 3 modes
        excel_format: format for 3 modes
    '''
    if ws_name not in counters[wb_name]: # Create:
        # Add worksheet:
        workbooks[wb_name].create_worksheet(ws_name)
        
        # Setup columns:
        workbooks[wb_name].column_width(ws_name, (
            #15, 
            15, 40, 20, 4,        
            11, 11, 11,
            50, 5, 15, 15,
            ))
            
        # Setup header title:
        counters[wb_name][ws_name] = 2 # Current line        
        workbooks[wb_name].write_xls_line(
            ws_name, counters[wb_name][ws_name], (
                #u'Catalogo', 
                u'Codice', u'Name', u'Modello ind.', u'UM',            
                u'Q.', u'Costo', u'Costo modello',                
                u'Dettaglio', u'Errore', u'Subtotale', u'Subtotale modello',
                ), excel_format[wb_name]['f_header'])
        counters[wb_name][ws_name] += 1
        totals[wb_name][ws_name] = [0.0, 0.0] # Total page (normal, template)
        
    return (
        workbooks[wb_name], # WS
        counters[wb_name][ws_name], # Counter
        )

for product in sorted(res):
    wb_name = product[0]
    ws_name = product[1]
    
    template = product[7]
    subtotal_bom = product[10]
    if template:
        template_name = template.default_code
        industrial = template.from_industrial
        subtotal_industrial = product[5] * industrial
    else:
        template_name = ''
        industrial = ''
        subtotal_industrial = ''

    if product[9]: # Error:
        text = excel_format[wb_name]['f_text_red']
        number = excel_format[wb_name]['f_number_red']
    else:
        text = excel_format[wb_name]['f_text']
        number = excel_format[wb_name]['f_number']
        
    Excel, row = get_page(wb_name, ws_name, counters, excel_format)    
    Excel.write_xls_line(ws_name, row, (
        #product[1], # Category
        product[2], # Code
        product[3], # Name
        template_name, # Template
        product[4], # UOM
        
        (product[5], number),
        (product[6], number),
        (industrial, number),
        
        product[8],
        'X' if product[9] else ' ',
        (subtotal_bom, number),
        (subtotal_industrial, number),        
        ), text)
    counters[wb_name][ws_name] += 1
    totals[wb_name][ws_name][0] += subtotal_bom or 0.0
    totals[wb_name][ws_name][1] += subtotal_industrial or 0.0

# -----------------------------------------------------------------------------
# Write total page:
# -----------------------------------------------------------------------------
ws_name = 'TOTALI'
for wb_name in totals:
    Excel = workbooks[wb_name]    
    text = excel_format[wb_name]['f_text']
    number = excel_format[wb_name]['f_number']

    # Add total page:
    row = 0
    workbooks[wb_name].create_worksheet(ws_name)
    workbooks[wb_name].column_width(ws_name, (40, 15, 15))
    workbooks[wb_name].write_xls_line(
        ws_name, row, (
            u'Categoria', u'Totale DB', u'Totale industriale'), 
            excel_format[wb_name]['f_header'])
            
    for category in totals[wb_name]:
        row += 1
        subtotal_bom = totals[wb_name][category][0]
        subtotal_industrial = totals[wb_name][category][1]
        # Write total in Total page:
        Excel.write_xls_line(ws_name, row, (
            category, 
            (subtotal_bom, number),
            (subtotal_industrial, number),
            ), text)

        # Write total in sheet:
        workbooks[wb_name].write_xls_line(
            category, 0, (
                u'Totale categoria', '', '', '', '', '', '', '', '',
                (subtotal_bom, number),
                (subtotal_industrial, number),
                ), text)

# -----------------------------------------------------------------------------
# Write not included:
# -----------------------------------------------------------------------------
ws_name = 'Non inclusi'
Excel = ExcelWriter('./non_presenti.xlsx', verbose=True)

# Add total page:
row = 0
Excel.create_worksheet(ws_name)
Excel.column_width(ws_name, (30, 15, 40))
Excel.write_xls_line(ws_name, row, (u'Categoria', u'Codice', u'Nome'))

for product in sorted(
        product_pool.browse(not_product_ids), 
        key=lambda x: (
            x.inventory_category_id.name if x.inventory_category_id else '', 
            x.default_code)):
    row += 1
    Excel.write_xls_line(ws_name, row, (
        product.inventory_category_id.name if product.inventory_category_id \
            else 'NON ASSEGNATA', 
        product.default_code or '',
        product.name,
        ))
        
del(Excel)
del(workbooks['final'])
del(workbooks['half'])
del(workbooks['material'])
