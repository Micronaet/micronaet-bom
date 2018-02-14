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


class SaleOrderCheckOcWizard(orm.TransientModel):
    ''' Wizard for extract OC check file
    '''
    _name = 'sale.order.check.oc.wizard'

    # --------------------
    # Wizard button event:
    # --------------------
    def action_done(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        if context is None: 
            context = {}        
        
        wiz_browse = self.browse(cr, uid, ids, context=context)[0]
        
        # Pool used:
        excel_pool = self.pool.get('excel.writer')
        sol_pool = self.pool.get('sale.order.line')      
        
        # ---------------------------------------------------------------------
        # Generate Excel file
        # ---------------------------------------------------------------------
        ws_name = 'Esploso OC rimanenti'
        ws = excel_pool.create_worksheet(ws_name)        
        row = 0
        excel_pool.column_width(ws_name, [
            20, 
            10, 10, 10,
            10, 20, 
            10, 20, 
            10, 20, 
            20, 10, 10, 
            20])
        excel_pool.write_xls_line(ws_name, row, [
            'OC', 
            'OC', 'B', 'Cons.',
            'Rim.', 'Prodotto', 
            'Q.', 'Semilavorato', 
            'Q.', 'Tessuto', 'Tot', 
            'Stato'
            ])
        
        # ---------------------------------------------------------------------
        # Check sale order line:
        # ---------------------------------------------------------------------
        sol_ids = sol_pool.search(cr, uid, [
            ('order_id.state', 'not in', ('draft', 'sent', 'cancel')),
            ('order_id.mx_closed', '=', False),            
            ('mx_closed', '=', False),            
            ], context=context)
        
        for sol in sol_pool.browse(cr, uid, sol_ids[:50], context=context):    
            product = sol.product_id
            
            # -----------------------------------------------------------------
            # Remain OC
            # -----------------------------------------------------------------
            oc = sol.product_uom_qty
            d = sol.delivered_qty
            b = sol.product_uom_maked_sync_qty
            if d > b:
                remain = oc - d
            else:
                remain = oc - b
                
            if not remain:
                continue # jump all produced / delivered line    
            # -----------------------------------------------------------------
            # Explode BOM 1
            # -----------------------------------------------------------------
            dyn_ids = product.dynamic_bom_line_ids
            if not dyn_ids:
                continue
            for bom1 in dyn_ids:
                # Only important category: 
                if not bom1.category_id.important:
                    continue
                hw_ids = bom1.product_id.half_bom_ids    
                
                # -------------------------------------------------------------
                # Explode BOM 2
                # -------------------------------------------------------------
                if not hw_ids:
                    continue
                    
                for bom2 in hw_ids:
                    bom2_code = bom2.product_id.default_code
                    if not bom2_code.startswith('T'):
                        continue # only T code
                    row += 1
                    excel_pool.write_xls_line(ws_name, row, [
                        sol.order_id.name, 
                        oc, b, d,
                        remain, product.default_code, 
                        bom1.product_qty, bom1.product_id.default_code,
                        bom2.product_qty, bom2_code, 
                        remain * bom1.product_qty * bom2.product_qty,
                        sol.order_id.state,
                        ])
                
        return excel_pool.return_attachment(cr, uid, 'Stampa esploso OC', 
            name_of_file='esploso_oc.xlsx', context=context)
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
