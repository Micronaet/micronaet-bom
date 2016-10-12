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

class SaleOrder(orm.Model):
    """ Model name: SaleOrder
    """    
    _inherit = 'sale.order'
    
    # -------------------------------------------------------------------------
    #                               UTILITY
    # -------------------------------------------------------------------------
    def get_component_in_product_order_open(
            self, cr, uid, all_product=False, logfile=False, context=None):
        ''' Check open order and return list of product present
            (for line not closed)
            all_product: True add all product also no structure and no compon.
            chose logfile if report need to log operation            
        '''
        line_pool = self.pool.get('sale.order.line')
        
        # ---------------------------------------------------------------------
        # Database:
        # ---------------------------------------------------------------------
        data = {
            # Data database
            'product': [], # database for product
            'component': [], # database for compoment
            # TODO 
            'order': [], # order header
            'line': [], # order line
            
            # Check error database:
            'no_product': [],
            'no_structure': [],
            'no_component': [],
            }
        
        # Search open order:
        line_ids = line_pool.search(cr, uid, [
            ('order_id.mx_closed', '=', False), # order open
            ('mx_closed', '=', False), # line open 
            ], context=context)

        for line in line_pool.browse(cr, uid, line_ids, context=context):            
            product = line.product_id # Readability:

            # -----------------------------------------------------------------
            # Check no product:
            # -----------------------------------------------------------------
            if not product:
                data['no_product'].append(line) # browse line no product
                continue
                
            structure = product.structure_id # Readability
                
            # -----------------------------------------------------------------
            # Check structure:            
            # -----------------------------------------------------------------            
            if not structure and product not in data['no_structure']:
                data['no_structure'].append(product)
                if all_product and product not in data['product']:
                    data['product'].append(product)
                continue
                
            # -----------------------------------------------------------------
            # Save for explode:
            # -----------------------------------------------------------------            
            if product not in data['product']:
                total = len(product.dynamic_bom_line_ids)
                                
                if not total:
                    data['no_component'].append(product)
                    if all_product and product not in data['product']:
                        data['product'].append(product)
                    continue

                # Read all component
                for line in product.dynamic_bom_line_ids:
                    component = line.product_id # XXX always present
                    if component not in data['component']:
                        data['component'].append(component)
                        
                if product not in data['product']:
                    data['product'].append(product)                        
        return data
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
