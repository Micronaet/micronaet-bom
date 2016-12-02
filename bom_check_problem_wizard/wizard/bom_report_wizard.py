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


class MrpBomCheckProblemWizard(orm.TransientModel):
    ''' Wizard for
    '''
    _name = 'mrp.bom.check.problem.wizard'

    # --------------------
    # Wizard button event:
    # --------------------
    def action_show_line_list(self, cr, uid, ids, context=None):
        ''' Show list in tree view (product in bom)
        '''
        # TODO 
        return True
        
    def action_show_list(self, cr, uid, ids, context=None):
        ''' Show list in tree view
        '''
        product_pool = self.pool.get('product.product')
        
        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]
        start_code = wiz_proxy.start_code or ''
        component = wiz_proxy.component or False

        product_ids = product_pool.search(cr, uid, [
            ('default_code', '=ilike', '%s%%' % start_code),
            ('relative_type', '=', 'half'),
            ], context=context)
        
        res_ids = []
        for product in product_pool.browse(
                cr, uid, product_ids, context=context):
            if not component or len(product.half_bom_ids) >= component:
                res_ids.append(product.id)
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Product list'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            #'res_id': 1,
            'res_model': 'product.product',
            'view_id': False,
            'views': [(False, 'tree'), (False, 'form')],
            'domain': [('id', 'in', res_ids)],
            'context': context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }
            
    def action_print(self, cr, uid, ids, context=None):
        ''' Event for button print
        '''
        if context is None: 
            context = {}        
        
        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        datas = {
            'from_wizard': True,
            'from_date': wiz_proxy.from_date or False,
            'to_date': wiz_proxy.to_date or False,
            'start_code': wiz_proxy.start_code or '',
            'from_order': wiz_proxy.from_order,
            'only': wiz_proxy.only,
            'modal': wiz_proxy.modal or False,
            'component': wiz_proxy.component,
            'no_bom_product': wiz_proxy.no_bom_product,
            }
        
        if wiz_proxy.mode == 'order':
            report_name = 'order_bom_component_check_report'        
        elif wiz_proxy.mode == 'parent':
            report_name = 'aeroo_parent_final_component_check_report'
        elif wiz_proxy.mode == 'product':
            report_name = 'aeroo_bom_all_component_check_report'
        elif wiz_proxy.mode == 'half':
            report_name = 'aeroo_hw_bom_all_component_check_report'
        elif wiz_proxy.mode == 'pipe':
            report_name = 'aeroo_pipe_bom_all_component_check_report'
        elif wiz_proxy.mode == 'line':
            report_name = 'aeroo_product_in_bom_report'
        else:
            _logger.error('No report mode %s!') % wiz_proxy.mode            

        return {
            'type': 'ir.actions.report.xml',
            'report_name': report_name,
            'datas': datas,
            }

    _columns = {
        'mode': fields.selection([
            ('order', 'Product BOM from order'),
            ('parent', 'Parent BOM'),
            ('product', 'Product result BOM'),
            ('half', 'Halfworked BOM'),            
            ('pipe', 'Pipe in Halfworked'),
            ('line', 'Product presence bom'),
            ], 'Report mode', required=True),            
            
        'from_order': fields.boolean('From order'),    
        
        'modal': fields.selection([
            ('pipe', 'Pipe layout'),   
            ], 'Report mode', required=False),

        'from_date': fields.date('From', help='Date >='),
        'to_date': fields.date('To', help='Date <'),        
        
        'start_code': fields.char('Start code', size=20),
        'component': fields.integer('> # component'),
        
        'only': fields.selection([
            ('all', 'All'),
            ('error', 'Only error'),
            ('override', 'Only error and overrided'),
            ], 'Only line', required=True),                
        'no_bom_product': fields.boolean('No BOM product'),    
        }

    _defaults = {
        'mode': lambda *x: 'order',
        'only': lambda *x: 'all',
        }    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
