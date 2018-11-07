#!/usr/bin/python
# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP) 
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<https://micronaet.com>)
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


class MrpBomPlaceholderCheckWizard(orm.TransientModel):
    ''' Wizard for mrp.bom.placeholder.check.wizard
    '''
    _name = 'mrp.bom.placeholder.check.wizard'

    # --------------------
    # Wizard button event:
    # --------------------
    def action_print(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        if context is None: 
            context = {}

        wiz_browse = self.browse(cr, uid, ids, context=context)[0]
        bom = wiz_browse.bom_id

        # Pool used:
        product_pool = self.pool.get('product.product')
        excel_pool = self.pool.get('excel.writer')

        # ---------------------------------------------------------------------
        # Generate format used:
        # ---------------------------------------------------------------------
        excel_pool.set_format()
        f_title = excel_pool.get_format(key='title')
        f_header = excel_pool.get_format(key='header')
        f_header90 = excel_pool.get_format(key='header90')
        f_text = excel_pool.get_format(key='text')
        f_text_red = excel_pool.get_format(key='bg_red')
        f_text_yellow = excel_pool.get_format(key='bg_yellow')
        f_number = excel_pool.get_format(key='number')

        row = 0
        excel_pool.write_xls_line(
            ws_name, row, header, default_format=f_header)
        
        row += 1
        for product in sorted(
                product_pool.browse(
                    cr, uid, product_ids, context=context), 
                    key=lambda x: x.default_code):
            
            line = [
                product.default_code or '',
                product.name or '',
                product.parent_bom_id.name or '',
                ]
            excel_pool.write_xls_line(
                ws_name, row, line, default_format=f_text)
            row += 1

        
        # B. Check sheet:
        ws_name = 'Controllo segnaposto'
        header = [
            ('Codice prodotto', f_header), 
            #('Nome prodotto', f_header), 
            ]
        width = [
            20, 
            #45,
            ]
        
        header_convert = {} # for col position
        col = 0 # Start column # 2
        for line in sorted(bom.bom_line_ids, key=lambda x: x.category_id.name):
            col += 1
            category = line.category_id
            header_convert[category.id] = col
            header.append(category.name)
            width.append(4)
        
        excel_pool.create_worksheet(name=ws_name)
        excel_pool.column_width(ws_name, width)
        excel_pool.row_height(ws_name, [0], height=120)

        # ---------------------------------------------------------------------
        # Product with bom selected
        # ---------------------------------------------------------------------
        product_ids = product_pool.search(cr, uid, [
            ('parent_bom_id', '=', bom.id),
            ], context=context)        

        # ---------------------------------------------------------------------
        # Write title / header    
        # ---------------------------------------------------------------------
        row = 0
        excel_pool.write_xls_line(
            ws_name, row, header, default_format=f_header90)

        row += 1
        empty_block = ['' for item in range(0, col)]
        import pdb; pdb.set_trace()
        for product in sorted(
                product_pool.browse(
                    cr, uid, product_ids, context=context), 
                    key=lambda x: x.default_code):
            line = [
                product.default_code or '',
                #product.name or '',
                ]
            line.extend(empty_block)
            for dynamic in product.dynamic_bom_line_ids:
                component = dynamic.product_id
                placeholder = component.bom_placeholder
                alternative = component.bom_alternative
                category_id = dynamic.category_id.id
                col = header_convert[category_id]
                
                if alternative or placeholder:
                    code = ''
                else:
                    code = component.default_code or ''

                if placeholder:
                    f_cell = f_text_red
                elif alternative:    
                    f_cell = f_text_yellow
                else:    
                    f_cell = f_text

                line[col] = (code, f_cell)
                
            excel_pool.write_xls_line(
                ws_name, row, line, default_format=f_text)
            row += 1

        # ---------------------------------------------------------------------
        # Product with different bom:
        # ---------------------------------------------------------------------
        product_ids = product_pool.search(cr, uid, [
            ('parent_bom_id', '!=', wiz_browse.bom_id.id),
            ('default_code', '=ilike', 
                '%s%%' % bom.product_tmpl_id.default_code),
            ], context=context)

        # ---------------------------------------------------------------------
        #                             Excel file:        
        # ---------------------------------------------------------------------
        # A. Sheet product without BOM parent:
        ws_name = 'Senza DB padre'
        header = [
            'Codice prodotto', 
            'Nome prodotto', 
            'DB',
            ]
        width = [20, 45, 20]
        
        excel_pool.create_worksheet(name=ws_name)
        excel_pool.column_width(ws_name, width)
        #excel_pool.row_height(ws_name, row_list, height=10)

        return excel_pool.return_attachment(cr, uid, 'Controllo DB')

    _columns = {
        'bom_id': fields.many2one(
            'mrp.bom', 'DB Padre', required=True),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
