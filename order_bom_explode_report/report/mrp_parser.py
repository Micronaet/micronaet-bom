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
import xlsxwriter # XLSX export
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
    default_days = 30
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
            
        days = data.get('days', self.default_days)
            
        return _('Active production for %s days') % days

    def get_object(self, data):
        ''' Search all MRP elements                
        '''
        _logger.info('START REPORT STOCK UNLOAD PRODUCTION')
        # Readability:    
        cr = self.cr
        uid = self.uid
        context = {}

        # ---------------------------------------------------------------------
        # Utility function:
        # ---------------------------------------------------------------------
        def write_xls_log(mode, log):
            ''' Write log in WS updating counter
            '''
            col = 0
            for item in log:
                self.WS[mode].write(self.counter[mode], col, item)
                col += 1
            self.counter[mode] += 1
            return
        
        # ---------------------------------------------------------------------
        # Utility function:
        # ---------------------------------------------------------------------
        def report_order_component(x):
            ''' Order for component in reporting
            ''' 
            if x[5] == 'green':
                return (1, x[0].default_code)
            elif x[5] == 'yellow':
                return (2, x[0].default_code)
            else: # red
                return (3, x[0].default_code)
                
        # ---------------------------------------------------------------------        
        # Read parameters:        
        # ---------------------------------------------------------------------        
        if data is None:
            data = {}
        days = data.get('days', self.default_days)
        first_supplier_id = data.get('first_supplier_id')

        # pool used:
        sol_pool = self.pool.get('sale.order.line') 
        mrp_pool = self.pool.get('mrp.production')
        
        reference_date = '2016-10-15 00:00:00' # TODO change used for now!!!!!!
        limit_date = '%s 23:59:59' % (
            datetime.now() + timedelta(days=days)).strftime(
                DEFAULT_SERVER_DATE_FORMAT)
        _logger.warning('Range period: MRP from %s, Max open MRP <= %s' % (
            reference_date, limit_date))

        # Database used:        
        mrp_db = {}
        mrp_unload = {} # Stock unload from MRP
        mrp_order = {} # Order opened
        delta_stock = {} # Consumed component in stock (assume start is 0)

        # ---------------------------------------------------------------------
        # XLS log export:        
        # ---------------------------------------------------------------------
        filename = '/home/administrator/photo/log/mrp_product.xlsx'
        WB = xlsxwriter.Workbook(filename)

        # Work Sheet:
        self.WS = {
            'mrp': WB.add_worksheet('MRP'),
            'order': WB.add_worksheet('Order'),
            }            
        # Row counters:
        self.counter = {'mrp': 1, 'order': 1}
            
        # ------------------
        # Write Header line:
        # ------------------
        headers = {
            'mrp': [
                'MRP', 'Data', 'Ordine', 'Prodotto', 'TODO', 'Componente', 
                'Q. TODO', 'Delta', 'Commento',
                ],
            'order': [ 
                'MRP', 'Data', 'Ordine', 
                'Prodotto', 'Q. Usata prod.', 'Q. TODO prod.',
                'Componente', 'Q. Usata comp.', 'Q. TODO comp.', 
                'Commento',
                ],
            }
        for mode, header in headers.iteritems():
            col = 0
            for h in header:
                self.WS[mode].write(0, col, h)
                col += 1

        # ---------------------------------------------------------------------
        # BLOCK A: PRODUCTION OPEN IN RANG: TODO production needed
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
        for mrp in mrp_pool.browse(cr, uid, mrp_ids, context=context):
            mrp_db[mrp] = {}
            
            for sol in mrp.order_line_ids:
                comment = ''
                
                # Total elements:
                qty = sol.product_uom_qty
                qty_maked = sol.product_uom_maked_sync_qty 
                qty_delivered = sol.delivered_qty
                
                # Depend on maked or delivery check:
                if qty_maked >= qty_delivered:
                    todo = qty - qty_maked
                else:    
                    todo = qty - qty_delivered
                if todo < 0.0:
                    comment += 'Over delivered'
                elif not todo:    
                    comment += 'All delivered'
                elif sol.mx_closed:
                    todo = 0.0 # closed    
                    comment += 'Forced closed'
                
                for component in sol.product_id.dynamic_bom_line_ids:                    
                    product = component.product_id
                        
                    # Total todo product    
                    if product not in mrp_db[mrp]: 
                        # This, Delta previous MRP
                        mrp_db[mrp][product] = [0.0, 0.0] 
                    if product.id not in delta_stock:
                        delta_stock[product.id] = 0.0
                        
                    # This order:
                    this_qty = todo * component.product_qty
                    mrp_db[mrp][product][0] += this_qty
                    
                    # Update delta with this unload
                    delta_stock[product.id] -= this_qty
                    
                    # Current delta stock saved in order component:
                    mrp_db[mrp][product][1] = delta_stock[product.id]
                    
                    write_xls_log('mrp', [
                        '%s [%s]' % (mrp.name, mrp.id), 
                        mrp.date_planned,
                        sol.order_id.name,
                        sol.product_id.default_code,
                        todo, # Product TODO 
                        product.default_code, # Component
                        this_qty,
                        delta_stock[product.id],
                        comment,                  
                        ])
                        
        # ---------------------------------------------------------------------
        # BLOCK B: ALL PRODUCTION: OC Total and unload maked
        # ---------------------------------------------------------------------
        # Search in all production from reference date:
        # 1. get produced element for unload stock
        # 2. get order remain in open mrp for total needed
        
        sol_ids = sol_pool.search(cr, uid, [
            # Linked to production # TODO remove?
            ('mrp_id', '!=', False),
            
            # Date range production:
            ('mrp_id.date_planned', '>=', reference_date),#XXX correct for now!
            ('mrp_id.date_planned', '<=', limit_date),
            ], context=context)
            
        sol_proxy = sol_pool.browse(cr, uid, sol_ids, context=context)
        for sol in sol_proxy:
            comment = ''
            qty = sol.product_uom_qty
            qty_maked = sol.product_uom_maked_sync_qty
            qty_delivered = sol.delivered_qty
            
            # Depend on maked or delivery check:
            if qty_maked >= qty_delivered:
                order_remain = qty - qty_maked
            else:    
                order_remain = qty - qty_delivered
                
            if order_remain < 0.0:
                comment += 'Over delivered'
            elif not order_remain:    
                comment += 'All delivered'
            elif sol.mx_closed:
                order_remain = 0.0 # closed    
                comment += 'Forced closed'
                
            for component in sol.product_id.dynamic_bom_line_ids:                    
                product = component.product_id
                
                # Maked (unload stock)
                if product.id not in mrp_unload:
                    mrp_unload[product.id] = 0.0    
                qty_maked_cmpt = qty_maked * component.product_qty           
                mrp_unload[product.id] -= qty_maked_cmpt
                
                # Remain (order total)
                if product.id not in mrp_order:
                    mrp_order[product.id] = 0.0                
                    
                # Done and cancel means no OC remain:    
                if sol.mrp_id.state in ('done', 'cancel'):
                    component_qty = 0.0 # for log
                else:    
                    component_qty = order_remain * component.product_qty
                    mrp_order[product.id] -= component_qty

                write_xls_log('order', [
                    sol.mrp_id.name, 
                    sol.mrp_id.date_planned,
                    sol.order_id.name,

                    # Product:
                    sol.product_id.default_code,
                    qty_maked, # Maked / Used
                    order_remain, # Remain order to produce
                    
                    # Component:
                    product.default_code, # Component
                    qty_maked_cmpt,
                    component_qty,

                    comment,
                    ])

        # ---------------------------------------------------------------------
        # BLOCK C: PREPARE FOR REPORT
        # ---------------------------------------------------------------------
        res = []
        for mrp in sorted(mrp_db, key=lambda x: (x.date_planned, x.id)):
            record = mrp_db[mrp]
            components = []
            mrp_status = 'green'
            for component, qty in record.iteritems():
                this_qty = qty[0]
                delta_stock_qty = qty[1]
                
                # Current stock = stock - mrp (previous unload) - delta TODO
                stock_today = mrp_unload.get(component.id, 0.0)
                stock_net_qty = component.mx_net_qty # XXX without mrp unload!
                stock = stock_net_qty + stock_today + delta_stock_qty
                oc_period = mrp_order.get(component.id, 0.0)   
                of = component.mx_of_in
                of_move = ''
                for move in component.mx_of_ids:
                    of_move += '%s (%s)\n' % (
                        int(move.product_uom_qty or 0.0), 
                        '%s-%s' % (
                            move.date_expected[8:10],
                             move.date_expected[5:7],
                             ) if move.date_expected else '?',
                        )
                
                if stock >= 0.0:
                    status = 'green'
                elif stock + of >= 0.0:
                    status = 'yellow'
                    if mrp_status == 'green':
                        mrp_status = 'yellow'
                else:    
                    status = 'red'
                    if mrp_status != 'red':
                        mrp_status = 'red'
                    
                # component, need, stock, OC period, OF, status
                components.append((
                    component, # 0. Component
                    this_qty, # 1. MRP net q.                    
                    stock, # 2. net stock after this order
                    oc_period, # 3. 
                    of, # 4. 
                    status, # 5. 
                    of_move, # 6.
                    stock_today, # 7. Stock net
                    stock_net_qty, # 8. Stock without mrp unload
                    ))
            res.append((
                mrp, 
                sorted(components, key=lambda x: report_order_component(x)), 
                mrp_status,
                ),
                )
        WB.close()         
        return res
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
