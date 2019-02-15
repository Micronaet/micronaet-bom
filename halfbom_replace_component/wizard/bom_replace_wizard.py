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


class MrpBomReplaceHwWizard(orm.TransientModel):
    ''' Wizard for
    '''
    _name = 'mrp.bom.replace.hw.wizard'

    # -------------------------------------------------------------------------
    # Utility:
    # -------------------------------------------------------------------------            
    def action_run_in_context_mode(self, cr, uid, ids, context=None):
        ''' Event for button print
        '''
        if context is None: 
            context = {}
        mode = context.get('wizard_mode', 'select')

        # Pool used:        
        bom_line_pool = self.pool.get('mrp.bom.line')
        excel_pool = self.pool.get('excel.writer')

        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        # Read parameter:
        select_id = wiz_proxy.select_id.id
        update_id = wiz_proxy.update_id.id
        qty = wiz_proxy.qty

        # ---------------------------------------------------------------------
        # Search line with product:
        # ---------------------------------------------------------------------
        bom_line_ids = bom_line_pool.search(cr, uid, [
            ('bom_id.bom_category', '=', 'half'), # Only halfbom
            ('product_id', '=', select_id), # Selected product
            ], context=context)

        # ---------------------------------------------------------------------
        # Search BOM touched:
        # ---------------------------------------------------------------------
        bom_ids = [line.bom_id.id for line in bom_line_pool.browse(
            cr, uid, bom_line_ids, context=context)]
        bom_ids = list(set(bom_ids))
        
        # ---------------------------------------------------------------------
        # Report mode: 
        # ---------------------------------------------------------------------
        if mode == 'excel':
            # Create Excel file:
            ws_name = 'Modificati'
            excel_pool.create_worksheet(ws_name)
            
            # Format:
            excel_pool.set_format()
            f_title = excel_pool.get_format('title')
            f_header = excel_pool.get_format('header')
            f_text = excel_pool.get_format('text')
            f_number = excel_pool.get_format('number')
            
            # Column setup:
            excel_pool.column_width(ws_name, [
                4, 15, 40, 30, 10, 30, 10])
            
            # Write header:    
            row = 0
            from_code = wiz_proxy.select_id.default_code
            to_code = wiz_proxy.update_id.default_code
            excel_pool.write_xls_line(ws_name, row, [
                'Aggiorna DB semilavorato, prodotto da %s a %s, con q. %s' % (
                    from_code,
                    to_code,
                    qty or '/',                    
                    )
                ], default_format=f_title)
            
            row += 1
            excel_pool.write_xls_line(ws_name, row, [
                'ID',
                'DB Codice',
                'DB Nome',
                'Vecchio Componente', 
                'Vecchia Q.', 
                'Nuovo componente', 
                'Nuova Q.' if qty else '',     
                ], default_format=f_header)
            
            
            for line in  bom_line_pool.browse(cr, uid, bom_line_ids, 
                    context=context):
                row += 1
                excel_pool.write_xls_line(ws_name, row, [
                    line.id,
                    line.bom_id.product_tmpl_id.default_code,
                    line.bom_id.product_tmpl_id.name,
                    line.product_id.default_code, 
                    line.product_qty, 
                    to_code, 
                    (qty or '/', f_number),
                    ], default_format=f_text)
            return excel_pool.return_attachment(
                cr, uid, 'Esito modifica', context=context)
        
        # ---------------------------------------------------------------------
        # Update mode: 
        # ---------------------------------------------------------------------
        if mode == 'update':
            data = {
                'product_id': update_id,
                }
            if qty:
                data['product_qty'] = qty 
            bom_line_pool.write(cr, uid, bom_line_ids, data, context=context)


        # ---------------------------------------------------------------------
        # Both select of update   
        # ---------------------------------------------------------------------
        return {
            'type': 'ir.actions.act_window',
            'name': _('DB Semilavorati'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            #'res_id': 1,
            'res_model': 'mrp.bom',
            'view_id': False,
            'views': [(False, 'tree'), (False, 'form')],
            'domain': [('id', 'in', bom_ids)],
            'context': context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }

    # -------------------------------------------------------------------------
    # Wizard button event:
    # -------------------------------------------------------------------------            
    def action_select(self, cr, uid, ids, context=None):
        ''' Select BOM with this filter
        '''
        if context is None: 
            context = {}
        context['wizard_mode'] = 'select'        
        return self.action_run_in_context_mode(cr, uid, ids, context=context)    

    def action_excel(self, cr, uid, ids, context=None):
        ''' Select BOM with this filter
        '''
        if context is None: 
            context = {}
        context['wizard_mode'] = 'excel'        
        return self.action_run_in_context_mode(cr, uid, ids, context=context)    

    def action_update(self, cr, uid, ids, context=None):
        ''' Update BOM with this filter
        '''
        if context is None: 
            context = {}
        context['wizard_mode'] = 'update'        
        return self.action_run_in_context_mode(cr, uid, ids, context=context)    

    _columns = {
        'select_id': fields.many2one(
            'product.product', 'Search', required=True),
        'update_id': fields.many2one(
            'product.product', 'Update'),
        'qty': fields.float('New Q.', digits=(16, 3)),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
