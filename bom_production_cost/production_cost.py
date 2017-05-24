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

class ProductProduct(orm.Model):
    """ Model name: Product
    """    
    _inherit = 'product.product'
    
    def update_family_medium_mrp_cost(self, cr, uid, ids, context=None):
        ''' Update family cost from statistics
        '''
        stat_pool = self.pool.get('mrp.production.stats')
        stats_db = {}
        stat_ids = stat_pool.search(cr, uid, [], context=context)
        for stat in stat_pool.browse(cr, uid, stat_ids, context=context):
            
        
        return True
        
    _columns = {
        'medium_mrp_cost': fields.float('Cost m(x)', digits=(16, 3),
            help='Medium cost of production for family',
            ),
        }
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
