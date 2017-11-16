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

bom_status = [
    ('used', 'Used (< 12)'),
    ('old', 'Old (12 > 24)'),
    ('obsolete', 'Obsolete (> 24)'),
    ]

class ProductProduct(orm.Model):
    """ Model name: ProductProduct
    """    
    _inherit = 'product.product'

    _columns = {
        'mrp_status': fields.selection(
            bom_status, 'MRP Status (product)'),
        'bom_line_status': fields.selection(
            bom_status, 'BOM line status (component)'),
        }

    _defaults = {
        # For new product (first schedule correct old elements)
        'mrp_status': lambda *x: 'used',
        'bom_line_status': lambda *x: 'used',
        }

class SaleOrderLine(orm.Model):
    """ Model name: Sale line
    """    
    _inherit = 'sale.order.line'
    
    # Utility:
    def _update_mrp_status(self, cr, uid, context=None):
        ''' Update only product mrp status
        '''
        # ---------------------------------------------------------------------
        # Utility:
        # ---------------------------------------------------------------------
        def update_product(self, cr, uid, domain, value, context=None):
            ''' Update product function
            '''
            _logger.info('Set product: %s' % value)
            product_pool = self.pool.get('product.product')
            
            sol_ids = self.search(cr, uid, domain, context=context)
            _logger.info('Row produced: %s' % len(sol_ids))
            
            for item in self.browse(cr, uid, sol_ids, context=context):
                if item.product_id:
                    product_pool.write(cr, uid, item.product_id.id, {
                        'mrp_status': value,
                        }, context=context)                        

            _logger.info('Update also product')
            return True

        # ---------------------------------------------------------------------
        # Prameters:            
        # ---------------------------------------------------------------------
        now = datetime.now() 
        month_12 = (now - timedelta(365)).strftime(
            DEFAULT_SERVER_DATETIME_FORMAT)
        month_24 = (now - timedelta(730)).strftime(
            DEFAULT_SERVER_DATETIME_FORMAT)

        # ---------------------------------------------------------------------
        #                   Mark product mrp status:
        # ---------------------------------------------------------------------
        # A. Reset product
        product_pool = self.pool.get('product.product')
        all_ids = product_pool.search(cr, uid, [], context=context)
        _logger.info('Reset product status: %s' % len(all_ids))
        product_pool.write(cr, uid, all_ids, {
            'mrp_status': False,
            'bom_line_status': False,
            }, context=context)

        # B. used (0 - 12)
        update_product(self, cr, uid, [
            ('mrp_id.state', '!=', 'cancel'),
            ('mrp_id.date_planned', '>=', month_12),
            ], 'used', context=context)

        # C. old (12 - 24)
        update_product(self, cr, uid, [
            ('mrp_id.state', '!=', 'cancel'),
            ('mrp_id.date_planned', '<', month_12),
            ('mrp_id.date_planned', '>=', month_24),
            ('product_id.mrp_status', '=', False),            
            ], 'old', context=context)

        # C. obsolete (24 - ..)
        update_product(self, cr, uid, [
            ('mrp_id.state', '!=', 'cancel'),
            ('mrp_id.date_planned', '<', month_24),
            ('product_id.mrp_status', '=', False),            
            ], 'obsolete', context=context)

        return True
    
    # Scheduled procedure:    
    def schedule_setup_obsolete_component_in_bom(self, cr, uid, context=None):
        ''' Setup obsolete component
        '''
        def sort_function(x):
            if x == 'obsolete': 
                return 3
            elif x == 'old':
                return 2
            else: # used
                return 1    
                
        product_pool = self.pool.get('product.product')

        # 1. Update product MRP status:
        # XXX self._update_mrp_status(cr, uid, context=context)
        
        # 2. Mark bom line status:
        update_db = {'old': [], 'updated': [], 'used': []}
        product_ids = product_pool.search(cr, uid, [
            ('mrp_status', '!=', False),
            ], context=context)
        _logger.info('Start explode %s product BOM' % len(product_ids))

        updated_ids = [] # for check (because there's an order)
        for product in sorted(product_pool.browse(cr, uid, product_ids, 
                context=context), key=lambda x: sort_function(x.mrp_status)):
            if product.id in updated_ids:
                continue # jump if yet updated (for order priorirty)

            # -----------------------------------------------------------------    
            # Mark all primary component:    
            # -----------------------------------------------------------------    
            updating_ids = update_db[product.mrp_status]
            for first in product.dynamic_bom_line_ids:
                item = first.product_id
                if item.id not in updating_ids:
                    updating_ids.append(item.id)
                    updated_ids.append(item.id)

                # -------------------------------------------------------------
                # Mark all primary component:    
                # -------------------------------------------------------------
                for second in item.half_bom_ids:
                    cmpt = second.product_id
                    if cmpt.id not in updating_ids:
                        updating_ids.append(cmpt.id)
                        updated_ids.append(cmpt.id)

        # ---------------------------------------------------------------------
        # Update operations:
        # ---------------------------------------------------------------------
        import pdb; pdb.set_trace()
        for status, item_ids in update_db.iteritems():
             product_pool.write(cr, uid, item_ids, {
                 'bom_line_status': status,
                 }, context=context)
        return True

class MrpBomLine(orm.Model):
    """ Model name: Bom lines
    """    
    _inherit = 'mrp.bom.line'
    
    _columns = {
        'bom_line_status': fields.related(
            'product_id', 'bom_line_status', selection=bom_status,
            type='selection', string='Bom line status'),
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
