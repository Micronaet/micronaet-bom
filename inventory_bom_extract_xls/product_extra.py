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

class ProductProduct(orm.Model):
    """ Model name: ProductProduct
    """
    
    _inherit = 'product.product'
    
    def get_purchase_cost_value(self, cr, uid, context=None):
        ''' Check price from purchase order after from 
        '''
        _logger.info('Check price from purchase')

        # ---------------------------------------------------------------------        
        # Start with supplier order price:
        # ---------------------------------------------------------------------        
        of_cost = {}
        po_pool = self.pool.get('purchase.order')
        po_ids = po_pool.search(cr, uid, [
            ('state', 'in', ('approved', )),
            #('date_order', '>=', '%s-01-01' % year),
            #('date_order', '<=', '%s-12-31' % year),
            ], order='date_order desc', context=context)
        
        for po in po_pool.browse(cr, uid, po_ids, context=context):
            for line in po.order_line:
                if not line.price_unit:
                    continue # jump no price line
                product = line.product_id
                default_code = product.default_code
                if default_code and default_code not in of_cost:                    
                    of_cost[default_code] = line.price_unit

        # ---------------------------------------------------------------------            
        # Load cost check costs:
        # ---------------------------------------------------------------------
        costs = {}
        product_pool = self.pool.get('product.product')
        _logger.info('Check price from check costs')

        log_file = os.path.join(os.path.expanduser('~'), 'price.csv')
        log_f = open(log_file, 'w')

        product_ids = product_pool.search(cr, uid, [
            ('default_code', '!=', False),
            ], context=context)
        for product in product_pool.browse(cr, uid, product_ids, 
                context=context):
            default_code = product.default_code            
            for seller in product.seller_ids:
                if default_code not in costs:
                    break
                    
                for pl in sorted(
                        seller.pricelist_ids, 
                        lambda x: x.date_quotation,
                        reverse=True):
                    costs[default_code] = pl.price
                    log_f.write('%s|%s|%s\n' % (
                        default_code, pl.price, pl.date_quotation))
                    break
                            
            # -----------------------------------------------------------------
            # Use anagraphic if not present
            # -----------------------------------------------------------------
            if not costs.get(default_code, False):
                costs[default_code] = \
                    of_cost.get(default_code, False) or product.standard_price
        return costs            
            
    _columns = {
        'inv_cost_account': fields.char('Inv. cost account', size=8),
        'inv_revenue_account': fields.char('Inv. cost account', size=8),
        'inv_first_supplier': fields.char('Inv. First supplier', size=8),        
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
