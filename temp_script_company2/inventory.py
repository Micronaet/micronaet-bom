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

from inventory_present import product_present

_logger = logging.getLogger(__name__)

class ResCompany(orm.Model):
    """ Model name: ResCompany
    """
    _inherit = 'res.company'

    # Procedure:    
    def save_cost_in_cost_method(self, cr, uid, ids, context=None):
        ''' Migrate 3 cost from old part in new cost management
        '''
        # Log operation
        log_file = '/home/administrator/photo/output/indoor_cost_migration.csv'
        f_log = open(log_file, 'w')
        
        product_pool = self.pool.get('product.product')
        product_ids = product_pool.search(cr, uid, [
            ('statistic_category', 'in', (
                'I01', 'I02', 'I03', 'I04', 'I05', 'I06')),
            ], context=context)
            
        f_log.write(
            'Codice|Cat. Stat.|Costo fornitore|Azienda Da|A|Cliente Da|A\n')
        for product in product_pool.browse(
                cr, uid, product_ids, context=context):
            f_log.write(
                '%s|%s|%s|%s|%s|%s|%s\n' % (
                    product.default_code,
                    product.statistic_category,
                    product.standard_price,
                    product.cost_in_stock,
                    product.company_cost,
                    product.cost_for_sale,
                    product.customer_cost,
                ))
            #product_pool.write(cr, uid, product.id, {
            #    'company_cost': product.cost_in_stock,
            #    'customer_cost': product.cost_for_sale,
            #    }, context=context)
    
