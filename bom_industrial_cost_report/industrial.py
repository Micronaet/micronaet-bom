# -*- coding: utf-8 -*-
###############################################################################
#
#    Copyright (C) 2001-2014 Micronaet SRL (<http://www.micronaet.it>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import os
import sys
import logging
import openerp
import openerp.netsvc as netsvc
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID, api
from openerp import tools
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)

class MrpBomIndustrialCost(orm.Model):
    """ Model name: Industrial cost
    """
    
    _name = 'mrp.bom.industrial.cost'
    _description = 'Industrial cost'
    _order = 'name'

    # -------------------------------------------------------------------------    
    # Button event:
    # -------------------------------------------------------------------------    
    def open_load_detail_list(self, cr, uid, ids, context=None):
        ''' Open list in tree view
        '''
        #model_pool = self.pool.get('ir.model.data')
        #view_id = model_pool.get_object_reference('module_name', 'view_name')[1]
        line_pool = self.pool.get('mrp.bom.industrial.cost.line')
        line_ids = line_pool.search(cr, uid, [
            ('cost_id', '=', ids[0]),
            ], context=context)
            
        return {
            'type': 'ir.actions.act_window',
            'name': _('Detail for cost selected'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'mrp.bom.industrial.cost.line',
            #'view_id': view_id, # False
            'views': [(False, 'tree'), (False, 'form')],
            'domain': [('id', 'in', line_ids)],
            'context': context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }
            
    def load_detail_from_BOM(self, cr, uid, ids, context=None):
        ''' Load all mask list from bom selected
        '''
        product_pool = self.pool.get('product.product')
        line_pool = self.pool.get('mrp.bom.industrial.cost.line')
        
        current_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        # Load current mask selected:
        current_mask = []
        for line in current_proxy.line_ids:
            current_mask.append(line.name)
        
        # Create only new elements:
        mask_ids = product_pool.search(cr, uid, [
            ('bom_selection', '=', True),
            ], context=context)
        if not mask_ids:
            raise osv.except_osv(
                _('Error:'), 
                _('Error product reference selected for BOM'),
                )
        for product in product_pool.browse(cr, uid, mask_ids, context=context):
            mask = '%s%%' % product.default_code
            if mask in current_mask:
                continue
                 
            line_pool.create(cr, uid, {
                'cost_id': current_proxy.id,
                'cost': current_proxy.default_cost,
                'name': mask,
                }, context=context) 
        return True
        
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'default_cost': fields.float('Default cost', digits=(16, 3),
            help='Default cost used when append imported BOM'),        
        'note': fields.text('Note'),
        }

class MrpBomIndustrialCostLine(orm.Model):
    """ Model name: Cost line
    """
    
    _name = 'mrp.bom.industrial.cost.line'
    _description = 'Industrial cost line'
    _order = 'name'
    
    _columns = {
        'name': fields.char('Mask', size=64, required=True, 
            help='Mask for code, use % for all, _ for replace one char'),
        'cost': fields.float('Cost', digits=(16, 3), required=True),
        'cost_id': fields.many2one(
            'mrp.bom.industrial.cost', 'Cost', 
            required=False),            
        }

class MrpBomIndustrialCost(orm.Model):
    """ Model name: Industrial cost
    """
    
    _inherit = 'mrp.bom.industrial.cost'
    
    _columns = {
        'line_ids': fields.one2many(
            'mrp.bom.industrial.cost.line', 'cost_id', 'Line'),
        }

class ProductProduct(orm.Model):
    """ Model name: ProductProduct
    """
    
    _inherit = 'product.product'
            
    # -------------------------------------------------------------------------    
    # Utility function:
    # -------------------------------------------------------------------------    
    def get_cost_industrial_for_product(self, cr, uid, ids, context=None):
        ''' Return all list of industrial cost for product passed
            ids: product ids XXX now is one!
        '''
        res = {}
        cost_pool = self.pool.get('mrp.bom.industrial.cost')
        cost_ids = cost_pool.search(cr, uid, [], context=context)
        cost_db = {}
        for cost in cost_pool.browse(
                cr, uid, cost_ids, context=context):
            cost_db[cost.id] = cost.name            
        
        for product in self.browse(cr, uid, ids, context=context):
            default_code = product.default_code
            if not default_code:
                continue

            query = '''
                SELECT cost_id, cost
                FROM mrp_bom_industrial_cost_line 
                WHERE '%s' ilike name
                ORDER BY length(name) desc;
                ''' % default_code
            cr.execute(query)

            # Update category element priority order len mask
            for item in cr.fetchall():
                cost_name = cost_db.get(item[0], '???')
                if cost_name not in res: # only the first 
                    res[cost_name] = item[1]            
        return res

    # -------------------------------------------------------------------------
    # Button for select
    # -------------------------------------------------------------------------
    def bom_selection_on(self, cr, uid, ids, context=None):
        '''
        '''
        return self.write(cr, uid, ids, {
            'bom_selection': True,          
            }, context=context)

    def bom_selection_off(self, cr, uid, ids, context=None):
        '''
        '''
        return self.write(cr, uid, ids, {
            'bom_selection': False,            
            }, context=context)                
            
    _columns = {
        'bom_selection': fields.boolean('BOM Selection'),
        'from_industrial': fields.float(
            'From industrial cost', digits=(16, 3)),
        'to_industrial': fields.float(
            'To industrial cost', digits=(16, 3)),            
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
