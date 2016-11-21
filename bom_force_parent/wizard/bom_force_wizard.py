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
    _name = 'mrp.bom.force.parent.wizard'

    # --------------------
    # Wizard button event:
    # --------------------
    def return_product_tree(self, cr, uid, ids, context=None):
        ''' Return list of product selected
        '''
        model_pool = self.pool.get('ir.model.data')
        tree_view_id = model_pool.get_object_reference(cr, uid, 
            'bom_dynamic_structured', 
            'view_product_product_dynamic_bom_tree')[1]
        form_view_id = model_pool.get_object_reference(cr, uid, 
            'bom_dynamic_structured', 
            'view_product_product_dynamic_bom_form')[1]
            
        return {
            'type': 'ir.actions.act_window',
            'name': _('Result for force'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            #'res_id': 1,
            'res_model': 'product.product',
            'view_id': tree_view_id,
            'views': [(tree_view_id, 'tree'), (form_view_id, 'form')],
            'domain': [('id', 'in', ids)],
            'context': context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }
                
    def get_product_ids(self, cr, uid, ids, context=None):
        ''' Get filter for have product list
        '''
        product_pool = self.pool.get('product.product')
        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]
        start_code = wiz_proxy.start_code
        return product_pool.search(cr, uid, [
            ('default_code', '=ilike', '%s%%' % start_code)], context=context)
    
    def action_get_selection(self, cr, uid, ids, context=None):
        ''' Get tree of selected product
        '''
        product_ids = self.get_product_ids(cr, uid, ids, context=context)
        return self.return_product_tree(cr, uid, product_ids, context=context)
                
    def action_print(self, cr, uid, ids, context=None):
        ''' Event for button print
        '''
        if context is None: 
            context = {}     

        product_pool = self.pool.get('product.product')
        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]
        parent_bom_id = wiz_proxy.parent_bom_id.id
        product_ids = self.get_product_ids(cr, uid, ids, context=context)

        product_pool.write(cr, uid, product_ids, {
            'parent_bom_id': parent_bom_id}, context=context)
        return self.return_product_tree(cr, uid, product_ids, context=context)

    _columns = {
        'start_code': fields.char('Start code', size=20, required=True),
        'parent_bom_id': fields.many2one(
            'mrp.bom', 'Parent bom', required=True),
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
