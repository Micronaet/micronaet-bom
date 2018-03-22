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


class StockMoveExtractCutWizard(orm.TransientModel):
    ''' Wizard for extract movement
    '''
    _name = 'stock.move.extract.cut.wizard'

    # --------------------
    # Wizard button event:
    # --------------------
    def action_done(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        if context is None: 
            context = {}        
        
        wiz_browse = self.browse(cr, uid, ids, context=context)[0]
        
        #  Pool used:
        excel_pool = self.pool.get('excel.writer')
        move_pool = self.pool.get('stock.move')
        
        ws_name = 'Movimenti taglio'
        excel_pool.create_worksheet(name=ws_name) 

        domain = [
            #('picking_id.state', '=', 'done'),
            ('picking_id.dep_mode', '=', 'cut'),
            ('picking_id.origin', '=', False), # CL no origin (SL has 'SL...')
            ]
        if wiz_browse.from_date:
            domain.append(
                ('picking_id.date', '>=', wiz_browse.from_date))    
        if wiz_browse.to_date:
            domain.append(
                ('picking_id.date', '<=', wiz_browse.to_date))
        if wiz_browse.start_code:
            domain.append(
                ('product_id.default_code', '=ilike', '%s%%' % \
                    wiz_browse.start_code))
        if wiz_browse.product_id:
            domain.append(
                ('product_id', '<=', wiz_browse.product_id.id))
                
        move_ids = move_pool.search(cr, uid, domain, context=context)
        
        # ---------------------------------------------------------------------
        # Start write Excel file:
        # ---------------------------------------------------------------------        
        # Layout:
        excel_pool.column_width(ws_name, [
            15, 20, 15, 30, 6,
            ]) 
            
        # Header
        row = 0
        excel_pool.write_xls_line(ws_name, row, [
            'documento',
            'data',
            'codice',
            'nome',
            'quant.',
            ],)# default_format=False)
            
        # Move lines:    
        for move in sorted(
                move_pool.browse(cr, uid, move_ids, context=context),
                key=lambda x: (
                    x.picking_id.date,
                    x.product_id.default_code,
                    )):
            row += 1        
            excel_pool.write_xls_line(ws_name, row, [
                move.picking_id.name,
                move.picking_id.date,
                move.product_id.default_code or '??',
                move.product_id.name or '',
                move.product_uom_qty,
                ],)# default_format=False)
                    
        return excel_pool.return_attachment(cr, uid, 'Movimenti di taglio', 
            context=context)
            
    _columns = {
        'from_date': fields.date('From'),
        'to_date': fields.date('To'),
        'start_code': fields.char('Start with', size=25),
        'product_id': fields.many2one('product.product', 'Product'),
        }
        
    _defaults = {
        }    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
