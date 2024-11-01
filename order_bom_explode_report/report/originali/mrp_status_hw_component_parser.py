#!/usr/bin/python
# -*- coding: utf-8 -*-
###############################################################################
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
###############################################################################
import os
import sys
import logging
import openerp
import xlsxwriter # XLSX export
import openerp.netsvc as netsvc
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from openerp import SUPERUSER_ID
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
            'get_parent_oc_period': self.get_parent_oc_period,
        })
        
    def get_parent_oc_period(self, parent):
        res = ''
        period = self.order_month.get(parent, {})
        for date in sorted(period):
            res += '[%s %s] ' % (date, period[date])
        return res
        
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
        ''' Search all mrp elements                
        '''
        # Readability:    
        cr = self.cr
        uid = self.uid
        context = {}

        user_pool = self.pool.get('res.users')
        previous_status = user_pool.set_no_inventory_status(
            cr, uid, value=False, context=context)
            
        # ---------------------------------------------------------------------
        #                                Utility:
        # ---------------------------------------------------------------------
        def log_line(self, line, extra=None, mode='product'):
            ''' Utility for log in excel file:
            '''
            if extra is None:
                extra = {}
                
            if mode == 'product':
                WS = self.WS[mode] 
                
                # -------------------------------------------------------------
                # Write header:
                # -------------------------------------------------------------
                if not self.counters[mode]:
                    counter = self.counters[mode]
                    header = [
                        # Reference:
                        'Parent', 'DB padre', 'Product', 'Order ref.',                    
                        # Order quantity:
                        #'OC') # MA
                        #'B' # B total
                        #'Delivery') # BC                    
                        # Quantity for accounting:
                        'Remain to MRP', # OC
                        'Ready', # B net
                        'Stock', # Stock
                        # Calculated data
                        'TODO',                        
                        # Check
                        'No BOM', 'Negative',
                        ]
                    header.extend(extra.keys())    
                        
                    col = 0
                    for h in header:
                        WS.write(counter, col, h)
                        col += 1
                    self.counters[mode] += 1
                    
                # -------------------------------------------------------------
                # Write data line:
                # -------------------------------------------------------------
                col = 0
                counter = self.counters[mode]
                
                # Write constant data:
                for item in line:
                    WS.write(counter, col, item)
                    col += 1
                # Write extra data:    
                for k in extra:
                    WS.write(counter, col, extra[k])
                    col += 1
                    
                self.counters[mode] += 1
            elif mode == 'halfwork':
                pass
            elif mode == 'component':
                pass
            elif mode == 'mrp':
                WS = self.WS[mode]                 
                # -------------------------------------------------------------
                # Write header:
                # -------------------------------------------------------------
                if not self.counters[mode]:
                    counter = self.counters[mode]
                    header = [
                        # Reference:
                        'MRP', 'OC', 'Code', 'Maked',
                        ]
                        
                    col = 0
                    for h in header:
                        WS.write(counter, col, h)
                        col += 1
                    self.counters[mode] += 1
                    
                # -------------------------------------------------------------
                # Write data line:
                # -------------------------------------------------------------
                col = 0
                counter = self.counters[mode]
                
                # Write constant data:
                for item in line:
                    WS.write(counter, col, item)
                    col += 1                    
                self.counters[mode] += 1
            else:
                pass # error                
            return
            
        # ---------------------------------------------------------------------
        #                                Procedure:
        # ---------------------------------------------------------------------

        self.order_month = {} # Parent distribution for month
                
        if data is None:
            data = {}

        # Log part
        # TODO change:
        filename = '/home/administrator/photo/log/parent_product.xlsx'
        WB = xlsxwriter.Workbook(filename)
        extra = {
            'code_check': '',
            'stock_check': '',
            }
            
        self.counters = {
            'product': 0,
            'halfwork': 0,
            'component': 0,
            'mrp': 0,
            }
        
        self.WS = {
            'product': WB.add_worksheet(),
            'halfwork': WB.add_worksheet(),
            'component': WB.add_worksheet(),
            'mrp': WB.add_worksheet(),
            }

        days = data.get('days', self.default_days)
        first_supplier_id = data.get('first_supplier_id')
        # Create deadline period in report:
        with_deadline = data.get('with_deadline', False) 
        
        # TODO change used for now!!!!!!
        #reference_date = '2016-10-15 00:00:00' 
        # 04/01/2017 Change after inventory
        reference_date = '2017-09-01 00:00:00' # TODO keep in parameter
        
        # TODO manage day range
        if days:
            limit_date = '%s 23:59:59' % (
                datetime.now() + timedelta(days=days)).strftime(
                    DEFAULT_SERVER_DATE_FORMAT)
        else:
            limit_date = False            

        # Pool used:
        company_pool = self.pool.get('res.company')
        sale_pool = self.pool.get('sale.order')
        #sol_pool = self.pool.get('sale.order.line') 
        mrp_pool = self.pool.get('mrp.production')
        
        _logger.warning('Range period: MRP from %s, Max open MRP <= %s' % (
            reference_date, limit_date or 'no limit'))

        # ---------------------------------------------------------------------        
        # To produce line in order open
        # ---------------------------------------------------------------------        
        # Database
        parent_todo = {}
        stock_used = [] # for product and halfwork
        hws = {}

        order_ids = company_pool.mrp_domain_sale_order_line(
            cr, uid, context=context)
        for order in sale_pool.browse(cr, uid, order_ids, context=context):
            for line in order.order_line: # order line
                # Reset log:
                extra['code_check'] = ''
                extra['stock_check'] = ''
                
                if line.mx_closed:
                    continue
                
                product = line.product_id # readability
                default_code = product.default_code
                if not default_code:
                    extra['code_check'] = 'no product code'
                    log_line(self, [
                        '', '', '', order.name, '', '', '', '', '', '',                        
                        ], extra)
                    continue # TODO raise error or log
                    
                parent = default_code[:3]
                if parent not in parent_todo:
                    # Stock, Order to produce, has stock negative
                    parent_todo[parent] = [
                        False, # 0. Parent bom for explode
                        0.0, # 1. Stock status net
                        0.0, # 2. Order to produce # merge with 1?
                        0, # 3. Stock status negative (total)
                        0, # 4. No parent bom (total)
                        0.0, # 5. Produce to delivery
                        ]

                # -------------------------------------------------------------    
                # Populate parent database:
                # -------------------------------------------------------------    
                # Setup parent bom fist time only (and check when not present):
                parent_bom = product.parent_bom_id
                if parent_bom and not parent_todo[parent][0]: 
                    # only once
                    parent_todo[parent][0] = parent_bom
                else:
                    if not parent_bom:
                        # Check no parent
                        parent_todo[parent][4] += 1
                    
                # ---------------------------------------
                # Stock check (use stock qty only once!):
                # ---------------------------------------
                if default_code not in stock_used:
                    extra['stock_check'] += 'used'
                    stock_used.append(default_code)
                    stock_net = product.mx_net_qty
                    # Check negative stock for highlight:
                    if stock_net < 0:
                        import pdb; pdb.set_trace()
                        parent_todo[parent][3] += 1
                    
                    parent_todo[parent][1] += stock_net # Net in stock (once)
                else:
                    extra['stock_check'] += 'not used'
                    stock_net = 0.0 # no used    
                
                # ---------------
                # Check negative:
                # ---------------
                # Use utility function:
                (oc_remain, not_delivered) = \
                    company_pool.mrp_order_line_to_produce(line)
                parent_todo[parent][2] += oc_remain
                parent_todo[parent][5] += not_delivered                
                
                # -------------------------------------------------------------    
                # Populate halfwork database:
                # -------------------------------------------------------------    
                todo = oc_remain # XXX - stock_net + not_delivered
                
                # Log line operation:
                log_line(self, [
                    parent, parent_bom.code or '???', default_code,
                    order.name, oc_remain, not_delivered, stock_net, todo,
                    '' if parent_bom else 'X', '' if stock_net >= 0 else 'X',      
                    ], extra)
                    
                # -------------------------------------------------------------    
                # Deadline calendar (depend on wizard, section in report):
                # -------------------------------------------------------------    
                if with_deadline and todo:
                    if parent not in self.order_month:
                        self.order_month[parent] = {}
                        
                    if line.date_deadline:
                        deadline_period = line.date_deadline[2:7]
                    else:        
                        deadline_period = '??'
                        
                    if deadline_period in self.order_month[parent]:
                        self.order_month[parent][deadline_period] += todo
                    else:    
                        self.order_month[parent][deadline_period] = todo

                # -------------------------------------------------------------
                # Halfwork from parent BOM
                # -------------------------------------------------------------
                for hw in parent_bom.bom_line_ids:
                    halfwork = hw.product_id
                    if halfwork.relative_type != 'half':
                        continue
                    if halfwork not in hws: # halfwork browse obj
                        hws[halfwork] = [
                            0.0, # 0. Needed                            
                            halfwork.mx_net_qty, # 1. Net (after - MRP) # TODO remove MRP ? 
                            {}, # 2. XXX total component for check double order?
                            # XXX No OF
                            ]

                    # Update total TODO * q. in BOM:
                    hws[halfwork][0] += todo * hw.product_qty
                    
                    # Save total for this bom (parent and halfwork) = key
                    # XXX used for not order double pipes?
                    hws[halfwork][2][
                        (parent, halfwork)] = hw.product_qty
                
        # ---------------------------------------------------------------------
        # Clean HW for unload production:
        # ---------------------------------------------------------------------        
        mrp_ids = mrp_pool.search(cr, uid, [
            # State filter:
            #('state', '!=', 'cancel'), # not correct !!!           
            # Period filter (only up not down limit)
            ('date_planned', '>=', reference_date),
            ], context=context)
            
        # Generate MRP total component report with totals:
        for mrp in mrp_pool.browse(cr, uid, mrp_ids, context=context):
            for sol in mrp.order_line_ids:
                product = sol.product_id                
                qty_maked = sol.product_uom_maked_sync_qty 
                # TODO better use dynamic_bom_line_ids ?
                # check existence                
                # Log product extract as MRP
                log_line(self, (
                    mrp.name, sol.order_id.name, product.default_code, 
                    qty_maked), mode='mrp')
                    
                for hw in product.parent_bom_id.bom_line_ids:
                    halfwork = hw.product_id
                    if halfwork.relative_type != 'half':
                        continue # Not used in this report
                        
                    if halfwork not in hws:                        
                        continue # TODO Raise error not in bom?
                        
                    hw_q = qty_maked * hw.product_qty
                    hws[halfwork][1] -= hw_q # - MRP # TODO check same problem
                    # TODO check if is bouble - MRP!!!
                    
        # ---------------------------------------------------------------------
        # Prepare report:
        # ---------------------------------------------------------------------
        res = []        

        # Empty record
        empty_A = ['' for n in range(0, 7)] # parent 7
        empty_B = ['' for n in range(0, 6)] # halfwork 6
        empty_C = ['' for n in range(0, 7)] # component 7
        
        hw_present = [] # for highlight only first total in report (for orders)
        for parent in sorted(parent_todo):
            record = parent_todo[parent]
            
            # -----------------------------------------------------------------
            #                             BLOCK A:
            # -----------------------------------------------------------------
            # Parent data:
            data_A = [
                parent, # 0. Code
                record[2], # 1. OC
                record[1], # 2. Mag (Net stock - MRP calculated)
                record[5], # 3. Produced to delivery
                record[2], # XXX ex.: - record[1] + record[5], # 4. todo
                record[3], # 5. tot. negative stock (for green-red light)
                record[4], # 6. tot. no bom (for green-red light)
                # TODO
                ]
                
            if not record[0]: # parent bom present:
                res.append(data_A + empty_B + empty_C)
                continue

            parent_first = True
            for hw in record[0].bom_line_ids:
                if not hw.product_id or hw.product_id.id in hw_present:
                    yet_write = True # yet write in report before
                else:
                    hw_present.append(hw.product_id.id)
                    yet_write = False # yet write in report before
                 
                if not hw.product_id in hws: # hw in the list selection
                    continue # not in selected list create before

                if parent_first:
                    parent_first = False                    
                else:    
                    data_A = empty_A # reset A
                    
                # -------------------------------------------------------------
                #                           BLOCK B:
                # -------------------------------------------------------------
                halfwork = hw.product_id # readability
                hw_data = hws.get(halfwork, False)
                if not hw_data:
                    res.append(data_A + empty_B + empty_C)
                    continue
                
                proposed_hw = hw_data[0] - hw_data[1]
                data_B = [
                    hw_data[2].get(
                        (parent, halfwork), '?'), # total
                    halfwork.default_code, # hw code
                    hw_data[0], # Todo halfwork
                    hw_data[1], # Stock
                    proposed_hw,
                    yet_write, # yet write status
                    ]
                
                hw_first = True
                for cmpt in halfwork.half_bom_ids:
                    if hw_first:
                        hw_first = False
                        data_AB = data_A + data_B
                    else:
                        data_AB = data_A + empty_B
                     
                    # ---------------------------------------------------------
                    #                  BLOCK C:
                    # ---------------------------------------------------------
                    cmpt_net = cmpt.product_id.mx_net_qty
                    cmpt_of = cmpt.product_id.mx_of_in       
                    proposed = \
                        proposed_hw * cmpt.product_qty - cmpt_net - cmpt_of

                    # Add data block directly:
                    res.append(data_AB + [
                        cmpt.product_qty, # total 
                        cmpt.product_id.default_code, # code
                        proposed_hw * cmpt.product_qty,
                        cmpt_net,
                        cmpt_of,
                        proposed if proposed > 0.0 else '',
                        proposed if proposed <= 0.0 else '',
                        ])
                            
                if hw_first: # no cmpt data (not in loop)
                    res.append(data_A + data_B + empty_C)
        user_pool.set_no_inventory_status(
            cr, uid, value=previous_status, context=context)            
        return res
        
