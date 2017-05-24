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

class MrpProductionEmployeeCost(orm.Model):
    """ Model name: MrpProductionmrp.production.
    """    
    _name = 'mrp.production.employee.cost'
    _description = 'Hour cost'
    _rec_name = 'name'
    _order = 'from_date'
    
    _columns = {
        'name': fields.char(
            'Description', size=64, required=True),
        'hour_cost': fields.float('Hour cost', digits=(16, 2), required=True),
        'from_date': fields.date('From date', required=True),
        }

class ProductTemplate(orm.Model):
    """ Model name: Product
    """    
    _inherit = 'product.template'
    
    def update_family_medium_mrp_cost(self, cr, uid, ids, context=None):
        ''' Update family cost from statistics
        '''
        # Utility:
        def get_hour_cost(hour_cost_db, date):
            ''' Search date in database and return correct hour cost for the
                period
            '''
            res = 10.0 
            return res
            
        # Pool used:
        stat_pool = self.pool.get('mrp.production.stats')
        cost_pool = self.pool.get('mrp.production.employee.cost')
        
        stats_db = {}
        stat_ids = stat_pool.search(cr, uid, [], context=context)

        # Get hour cost:
        cost_ids = cost_pool.search(cr, uid, [], context=context)
        if not cost_ids:
            raise osv.except_osv(
                _('No hour cost'), 
                _('Insert cost in MRP cost management'),
                )
        hour_cost_db = {}
        for cost in cost_pool.browse(cr, uid, cost_ids, context=context):
            hour_cost_db[cost.from_date] = cost.hour_cost    
        
        # TODO remove:    
        hour_cost = cost_pool.browse(
            cr, uid, cost_ids, context=context)[0].hour_cost
                        
        # Get total data:
        for stat in stat_pool.browse(cr, uid, stat_ids, context=context):
            product_id = stat.mrp_id.product_id.id # Family
            if product_id not in stats_db:
                stats_db[product_id] = [0, 0]
            stats_db[product_id][1] += stat.total
            # TODO reactivate:
            #hour_cost = get_hour_cost(hour_cost_db, stat.date)
            stats_db[product_id][0] += stat.workers * hour_cost * stat.hour   
          
        # Get unit cost:
        for product_id in stats_db:
            total_cost, total_hour = stats_db[product_id]
            if not total_hour:
                _logger.error('Jump division per 0 product: %s' % product_id)
                continue
                
            self.write(cr, uid, product_id, {
                'medium_mrp_cost': total_cost / total_hour,
                }, context=context)
        return True
        
    _columns = {
        'medium_mrp_cost': fields.float('Cost m(x)', digits=(16, 3),
            help='Medium cost of production for family',
            ),
        'medium_mrp_cost_forced': fields.float('Forced Cost m(x)', 
            digits=(16, 3), help='Medium cost of production for family froced',
            ),
        }
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
