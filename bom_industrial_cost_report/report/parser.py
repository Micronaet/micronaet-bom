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
import openerp.netsvc as netsvc
import openerp.addons.decimal_precision as dp
from openerp.report import report_sxw
from openerp.report.report_sxw import rml_parse
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)


class Parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(Parser, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'get_objects': self.get_objects,
            'get_details': self.get_details,
            'get_totals': self.get_totals,
        })
        
    def get_objects(self, data=None):
        ''' Return single report or list of selected bom 
        '''        # Readability:
        cr = self.cr
        uid = self.uid
        context = {}
        if data is None:
            data = {}

        # Pool used:    
        product_pool = self.pool.get('product.product')
        
        active_ids = data.get('active_ids', False)            
        if not active_ids:
            active_ids = product_pool.search(cr, uid, [
                ('bom_selection', '=', True),
                ], context=context)
        objects = product_pool.browse(
            cr, uid, active_ids, context=context)
           
        return objects #sorted(objects, key=lambda o: o.default_code)

    def get_details(self, product):
        ''' Create detail row
        '''
        res = {}
        
        # Min / Max totals:
        self.min = 0.0
        self.max = 0.0
        for item in product.dynamic_bom_line_ids:
            res[item] = []
            max_value = 0.0
            min_value = 0.0
            for seller in item.product_id.seller_ids:
                 for pricelist in seller.pricelist_ids:
                     if not pricelist.is_active:
                         continue
                     total = pricelist.price * item.product_qty
                     res[item].append((
                         seller.name.name,
                         '%10.5f' % pricelist.price,
                         pricelist.date_quotation or '???',
                         '%10.5f' % total,
                         ))
                     if not min_value or total < min_value:
                         min_value = total
                     if total > max_value:
                         max_value = total
            self.min += min_value
            self.max += max_value
            
        # Add lavoration cost:
        mrp_cost = product.family_id.medium_mrp_cost_forced or\
            product.family_id.medium_mrp_cost
        self.min += mrp_cost
        self.max += mrp_cost
            
        return res.iteritems()
        
    def get_totals(self, mode):
        ''' Total value (min or max)
        '''    
        if mode == 'min':
            return self.min
        else:
            return self.max
        return 