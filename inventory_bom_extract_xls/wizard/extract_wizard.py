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
import logging
import openerp
import xlsxwriter
import xlrd
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID
from openerp import tools
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)


class ProductInventoryExtractXLSWizard(orm.TransientModel):
    ''' Wizard for extracting inventory wizard
    '''
    _name = 'product.inventory.extract.xls.wizard'

    # --------------------
    # Wizard button event:
    # --------------------
    def action_extract(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        # ---------------------------------------------------------------------
        # Utility:
        # ---------------------------------------------------------------------
        def xls_write_row(WS, row, line, title=False, inventory=False):
            ''' Write row in a file
            '''
            if title: # data line
                WS.write(row, 0, title)
                WS.write(row, 1, inventory)                
                col = 1
            else: # header line:
                col = -1
                
            for item in line:
                col += 1
                WS.write(row, col, item)
            return
        
        def xls_sheet_write(WB, name, inventory):
            ''' Add new sheet and write inventory data
            '''
            WS = WB.add_worksheet(name)
            xls_write_row(WS, 0, [
                'Codice', 'Inv. iniz.', 'Gen.', 'Feb.', 'Mar.', 'Apr.', 'Mag.', 
                'Giu.', 'Lug.', 'Ago.', 'Set.', 'Ott.', 'Nov.', 'Dic.', 
                'Inv. fin.'
                ])
            row = 0
            for default_code in sorted(inventory):
                row += 1
                xls_write_row(WS, row, inventory[default_code], default_code)
            _logger.info('End extract %s sheet: %s' % (xls_file, name))
            return            
            
        if context is None: 
            context = {}    
            
        # Parameters:        
        code_part = 5
        xls_file = '/home/administrator/photo/xls/stock/inventory_%s.xlsx'
        xls_infile = '/home/administrator/photo/xls/stock/use_inv_%s.xlsx'

        
        # Read parameter from wizard:
        wiz_browse = self.browse(cr, uid, ids, context=context)[0]
        year = wiz_browse.year
        
        # Insert year in filename:
        xls_file = xls_file % year
        xls_infile = xls_infile % year

        # Open XLS file:
        _logger.info('Create extract %s file' % xls_file)
        WB = xlsxwriter.Workbook(xls_file)

        # ---------------------------------------------------------------------
        # Read parent code in invoice
        # ---------------------------------------------------------------------
        _logger.info('Start extract sale from invoice, year %s' % year)
        line_pool = self.pool.get('account.invoice.line')
        line_ids = line_pool.search(cr, uid, [
            ('invoice_id.date_invoice', '>=', '%s-01-01' % year),
            #('invoice_id.date_invoice', '<', '%s-02-01' % year),
            ('invoice_id.date_invoice', '<', '%s-01-01' % (year +1)),
            ('invoice_id.state', '=', 'open'),
            ], context=context)
            
        inventory = {}    
        _logger.info('Read %s invoice line' % len(line_ids))        
        for line in line_pool.browse(
                cr, uid, line_ids, context=context):
            default_code = line.product_id.default_code[:code_part] 
            quantity = line.quantity
            date_invoice = line.invoice_id.date_invoice
            
            if default_code not in inventory:
                inventory[default_code] = [
                    0, # Start inv.
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                    0, # End inv.
                    ]
            month = int(date_invoice[5:7])
            inventory[default_code][month] += quantity   

        # Export in XLSX file:
        xls_sheet_write(WB, 'Stock', inventory)
        
        # ---------------------------------------------------------------------
        # Integrate unload inventory:
        # ---------------------------------------------------------------------
        
        

    _columns = {
        'year': fields.integer('Year', required=True),
        }
        
    _defaults = {
        'year': lambda *x: int(datetime.now().strftime('%Y')),
        }    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:


