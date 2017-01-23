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

    def lavoration_inventory_modification(self, cr, uid, ids, context=None):
        ''' Export data from lavoration
        '''
        out_file = '/home/administrator/photo/output/lavoration_problem.csv'
        out_f = open(out_file, 'w')
        _logger.warning('Export lavoration problem: %s' % out_file)
        
        pick_pool = self.pool.get('stock.picking')
        pick_ids = pick_pool.search(cr, uid, [], context=context)
            
        for pick in pick_pool.browse(cr, uid, pick_ids, context=context):
            for line in pick.sl_quants_ids:
                out_f.write('%s|%s|%s|%s|%s|%s\n' % (
                    # Header:
                    pick.name,
                    pick.create_date,
                    pick.write_date,
                    pick.date,
                    # Line:
                    line.product_id.default_code,
                    line.qty,
                    ))
        _logger.warning('End export lavoration')
        out_f.close()
        return True
    
    def inventory_to_reset(self, cr, uid, ids, context=None):
        ''' Check error during operation on bom
        '''
        out_file = '/home/administrator/photo/log/product_to_reset'
        out_file_jump = '/home/administrator/photo/log/product_to_reset_jumped'
        
        out_f = open(out_file, 'w')
        out_jump = open(out_file_jump, 'w')
        
        # Pool used:
        product_pool = self.pool.get('product.product')

        # Check HW bon link:
        product_ids = product_pool.search(cr, uid, [
            ('default_code', 'not in', product_present),                     
            ], context=context)

        for product in product_pool.browse(
                cr, uid, product_ids, context=context):                
            if not product.default_code or product.default_code[:1] not in \
                    '1234567890G':                    
                out_jump.write('%s|0\n' % product.default_code)
                continue     
                    
            out_f.write('%s|0\n' % product.default_code)
        out_f.close()
        out_jump.close()        
