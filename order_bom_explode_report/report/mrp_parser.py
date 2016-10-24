#!/usr/bin/python
# -*- coding: utf-8 -*-
##############################################################################
#
#   Copyright (C) 2010-2012 Associazione OpenERP Italia
#   (<http://www.openerp-italia.org>).
#   Copyright(c)2008-2010 SIA "KN dati".(http://kndati.lv) All Rights Reserved.
#                   General contacts <info@kndati.lv>
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
import os
import sys
import logging
import openerp
import openerp.netsvc as netsvc
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from openerp import SUPERUSER_ID#, api
from openerp import tools
from openerp.report import report_sxw
from openerp.report.report_sxw import rml_parse
from datetime import datetime, timedelta
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)

_logger = logging.getLogger(__name__)

class Parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):        
        super(Parser, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'get_object': self.get_object,
            'get_filter': self.get_filter,
            'get_date': self.get_date,
        })

    def get_date(self, ):
        ''' Get filter selected
        '''
        return datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)

    def get_filter(self, data):
        ''' Get filter selected
        '''
        if data is None:
            data = {}
        return '' # TODO

    def get_object(self, data):
        ''' Search all mpr elements                
        '''
        # Readability:    
        cr = self.cr
        uid = self.uid
        context = {}
        
        if data is None:
            data = {}
        days = data.get('days', 30)
        
        mrp_db = {}
        
        # pool used:
        sol_pool = self.pool.get('sale.order.line') 
        mrp_pool = self.pool.get('mrp.production')
        
        reference_date = '2016-10-15 00:00:00' # TODO change used for now!!!!!!
        limit_date = '%s 23:59:59' % (
            datetime.now() + timedelta(days=days)).strftime(
                DEFAULT_SERVER_DATE_FORMAT)
        _logger.warning('Range period: MRP from %s, Max open MRP <= %s' % (
            reference_date, limit_date))
        
        mrp_unload = {} # Stock unload from MRP
        mrp_order = {} # Order opened
        previous_order = {} # Order opened incremental on date_planned
        
        # ---------------------------------------------------------------------
        #                      PRODUCTION OPEN IN RANGE:
        # ---------------------------------------------------------------------
        # Prepare data for remain production component
        # Update mrp stock with used halfword in productions
        
        mrp_ids = mrp_pool.search(cr, uid, [
            # State filter:
            ('state', 'not in', ('done', 'cancel')),
            
            # Period filter (only up not down limit)
            ('date_planned', '<=', limit_date),
            ], order='date_planned, id', context=context)
            
        # Generate MRP total componet report with totals:
        #product_ids = [] # list of product depend on mrp selected
        for mrp in mrp_pool.browse(cr, uid, mrp_ids, context=context):
            # TODO Check active state?
            mrp_db[mrp] = {}
            
            for sol in mrp.order_line_ids:
                # Total elements:
                qty = sol.product_uom_qty
                qty_maked = sol.product_uom_maked_sync_qty 
                todo = qty - qty_maked
                
                # Product selected in productions:
                #if sol.product_id.id not in product_ids:
                #    product_ids.append(sol.product_id.id)
                
                # Explode component:
                for component in sol.product_id.dynamic_bom_line_ids:                    
                    product = component.product_id
                        
                    # Total todo product    
                    if product not in mrp_db[mrp]: 
                        mrp_db[mrp][product] = [0.0, 0.0] # this, previous MRP
                    if component.id not in previous_order:
                        previous_order[component.id] = 0.0
                        
                    # This order:
                    this_qty = todo * component.product_qty
                    mrp_db[mrp][product][0] += this_qty
                    
                    # Previous ordered:
                    mrp_db[mrp][product][1] = previous_order[component.id]
                    
                    # Update previous ordered with this:
                    previous_order[component.id] -= this_qty

        # ---------------------------------------------------------------------
        #                           ALL PRODUCTION:
        # ---------------------------------------------------------------------
        # Search in all production from reference date:
        # 1. get produced element for unload stock
        # 2. get order remain in open mrp for total needed
        
        sol_ids = sol_pool.search(cr, uid, [
            # Linked to production # TODO remove?
            ('mrp_id', '!=', False),
            
            # Product used:
            #('mrp_id.state', 'in', ('done', 'cancel')), # also cancel
            #('product_id', 'in', product_ids), # only component used in report
            
            # Date range production:
            ('mrp_id.date_planned', '>=', reference_date),
            ('mrp_id.date_planned', '<=', limit_date),
            ], context=context)
            
        sol_proxy = sol_pool.browse(cr, uid, sol_ids, context=context)
        for sol in sol_proxy:
            qty = sol.product_uom_qty
            qty_maked = sol.product_uom_maked_sync_qty
            todo = qty - qty_maked
            
            for component in sol.product_id.dynamic_bom_line_ids:                    
                product = component.product_id
                
                # Maked (unload stock)
                if product.id not in mrp_unload:
                    mrp_unload[product.id] = 0.0                    
                mrp_unload[product.id] -= qty_maked * component.product_qty
                
                # Remain (todo order)
                if product.id not in mrp_order:
                    mrp_order[product.id] = 0.0                
                if sol.mrp_id.state not in ('done', 'cancel'): # only active
                    mrp_order[product.id] -= todo * component.product_qty

        # ---------------------------------------------------------------------
        #                           PREPARE FOR REPORT:
        # ---------------------------------------------------------------------
        res = {}
        for mrp in mrp_db.keys():
            record = mrp_db[mrp]
            res[mrp] = []
            for component, qty in record.iteritems():
                this_qty = qty[0]
                prev_qty = qty[1]
                
                stock = component.mx_net_qty + \
                    mrp_unload.get(component.id, 0.0)# + prev_qty
                    
                # component, need, stock, OC period, OF, status
                res[mrp].append((
                    component, # Component
                    this_qty, # MRP net q.
                    #Stock-MRP:
                    stock, # net stock with this order
                    mrp_order.get(component.id, 0.0), # MRP OC period
                    component.mx_of_in,
                    '?'))
        return res
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
