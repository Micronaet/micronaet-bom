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
        from_date = wiz_browse.from_date

        # Pool used:
        product_pool = self.pool.get('product.product')
        excel_pool = self.pool.get('excel.writer')

        # ---------------------------------------------------------------------
        # Generate format used:
        # ---------------------------------------------------------------------
        # A. Check sheet:
        ws_name = 'Controllo segnaposto'
        excel_pool.create_worksheet(name=ws_name)

        excel_pool.set_format()
        f_title = excel_pool.get_format(key='title')
        f_header = excel_pool.get_format(key='header')
        f_header90 = excel_pool.get_format(key='header90')
        f_text = excel_pool.get_format(key='text')
        f_text_red = excel_pool.get_format(key='bg_red')
        f_text_yellow = excel_pool.get_format(key='bg_yellow')
        f_number = excel_pool.get_format(key='number')

        header = [
            ('Codice prodotto', f_header), 
            ]
        width = [
            20, 
            ]

        # ---------------------------------------------------------------------
        # Product with bom selected
        # ---------------------------------------------------------------------
        all_ids = product_pool.search(cr, uid, [
            ('parent_bom_id', '=', bom.id),
            ], context=context)        

        if from_date:
            # Get list of invoiced product from that date:
            line_pool = self.pool.get('account.invoice.line')
            line_ids = line_pool.search(cr, uid, [
                ('product_id', 'in', all_ids), # Selected product
                ('account_id.date_invoice', '>=', from_date), # Period
                ], context=context)
                
            product_set_ids = set(
                [item.product_id.id for item in line_pool.browse(
                    cr, uid, line_ids, context=context)])
            product_ids = list(product_set_ids)
            not_in_ids = set(all_ids) - product_set_ids
        else:
            product_ids = all_ids    

        header_convert = {} # for col position
        position = 0 # Start column # 2
        for line in sorted(bom.bom_line_ids, key=lambda x: x.category_id.name):
            position += 1
            category = line.category_id
            header_convert[category.id] = position
            header.append(category.name)
            width.append(6)

        header.append('MANCANTI')
        position += 1
        
        excel_pool.column_width(ws_name, width)
        excel_pool.row_height(ws_name, [0], height=120)

        # ---------------------------------------------------------------------
        # Write title / header    
        # ---------------------------------------------------------------------
        row = 0
        excel_pool.write_xls_line(
            ws_name, row, header, default_format=f_header90)

        row += 1
        empty_block = ['' for item in range(0, position)]
        
        error_col = position + 2 # also detault colum)
        for product in sorted(
                product_pool.browse(
                    cr, uid, product_ids, context=context), 
                    key=lambda x: x.default_code):
            line = [
                product.default_code or ' ',
                ]
            line.extend(empty_block)

            for dynamic in product.dynamic_bom_line_ids:
                component = dynamic.product_id
                placeholder = component.bom_placeholder
                alternative = component.bom_alternative
                category_id = dynamic.category_id.id
                
                # Write category not present in extra columns:
                if category_id in header_convert:
                    col = header_convert[category_id]
                else:
                    line[-1] += _(u'[%s] ') % \
                        dynamic.category_id.name
                    continue # Error code

                code = component.default_code or ' '

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

        # B. Sheet product without BOM parent:
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

        # ---------------------------------------------------------------------
        # Product with different bom:
        # ---------------------------------------------------------------------
        product_ids = product_pool.search(cr, uid, [
            ('parent_bom_id', '!=', wiz_browse.bom_id.id),
            ('default_code', '=ilike', 
                '%s%%' % bom.product_tmpl_id.default_code),
            ], context=context)
        _logger.warning('Product not associated: %s' % len(product_ids))    

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

        # ---------------------------------------------------------------------
        # Product old
        # ---------------------------------------------------------------------
        if from_date and not_in_ids:
            _logger.warning('Product obsolete: %s' % len(not_in_ids))    
            # C. Obsolete product:
            ws_name = 'Obsoleti'
            header = [
                'Codice prodotto', 
                'Nome prodotto', 
                ]
            width = [20, 45]

            excel_pool.create_worksheet(name=ws_name)
            excel_pool.column_width(ws_name, width)

            row = 0
            excel_pool.write_xls_line(
                ws_name, row, header, default_format=f_header)
            
            row += 1
            for product in sorted(
                    product_pool.browse(
                        cr, uid, not_in_ids, context=context), 
                        key=lambda x: x.default_code):
                
                line = [
                    product.default_code or '',
                    product.name or '',
                    product.parent_bom_id.name or '',
                    ]
                excel_pool.write_xls_line(
                    ws_name, row, line, default_format=f_text)
                row += 1
                
        return excel_pool.return_attachment(cr, uid, 'Controllo DB')

    _columns = {
        'bom_id': fields.many2one(
            'mrp.bom', 'DB Padre', required=True),
        'from_date': fields.date('Dalla data', 
            help='Mostra solo i prodotti che hanno fatture dalla data',
            ),
        }

    _default = {
        'from_date': lambda *x: (
            datetime.now() - timedelta(days=365 * 3)).strftime(
                DEFAULT_SERVER_DATE_FORMAT),
        }    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
