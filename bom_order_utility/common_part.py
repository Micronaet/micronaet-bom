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

class ResCompany(orm.Model):
    """ Model name: ResCompany
    """
    
    _inherit = 'res.company'
    
    # -------------------------------------------------------------------------
    # Utility for report generation:
    # -------------------------------------------------------------------------
    def mrp_domain_sale_order_line(self, cr, uid, context=None):
        ''' Active order line with production extend
        '''
        sale_pool = self.pool.get('sale.order')
        order_ids = sale_pool.search(cr, uid, [
            ('state', 'not in', ('cancel', 'send', 'draft')),
            ('pricelist_order', '=', False),
            ('mx_closed', '=', False), # Only open orders (not all MRP after)
            # Also forecasted order
            # No filter date TODO use over data for reporting extra
            # XXX no x axis filter!
            ])
            
        # Add forecasted draft order (not in closed production)
        forecasted_ids = sale_pool.search(cr, uid, [
            ('forecasted_production_id', '!=', False),
            ('forecasted_production_id.state', 'not in', ('done', 'cancel')),
            ])
        order_ids.extend(forecasted_ids) # XXX no double FC is draft mode
        return order_ids 

    def mrp_domain_sale_order_line_ids(self, cr, uid, context=None):
        ''' Active order line with production extend
        '''
        order_ids = self.mrp_domain_sale_order_line(cr, uid, context=context)
        sol_pool = self.pool.get('sale.order.line')
        sol_ids = sol_pool.search(cr, uid, [
            ('order_id', 'in', order_ids),
            ('mx_closed', '=', False),
            ], context=context)
        # TODO filter product return     
        return sol_ids
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
