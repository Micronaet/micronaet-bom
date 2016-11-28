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
        ''' Search all mpr elements                
        '''
        # Readability:    
        cr = self.cr
        uid = self.uid
        context = {}
                
        if data is None:
            data = {}

        days = data.get('days', self.default_days)
        first_supplier_id = data.get('first_supplier_id')
        
        # TODO change used for now!!!!!!
        reference_date = '2016-10-15 00:00:00' 
        
        # TODO manage day range
        if days:
            limit_date = '%s 23:59:59' % (
                datetime.now() + timedelta(days=days)).strftime(
                    DEFAULT_SERVER_DATE_FORMAT)
        else:
            limite_date = False            

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
        hws = {}

        order_ids = company_pool.mrp_domain_sale_order_line(
            cr, uid, context=context)
        for order in sale_pool.browse(cr, uid, order_ids, context=context):
            for line in order.order_line: # order line
                if line.mx_closed:
                    continue
                product = line.product_id # readability
                default_code = product.default_code
                if not default_code:
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
                        ]
                    
                # -------------------------------------------------------------    
                # Populate parent database:
                # -------------------------------------------------------------    
                # Parent:
                parent_bom = product.parent_bom_id
                if parent_bom and not parent_todo[parent][0]: 
                    # only once
                    parent_todo[parent][0] = parent_bom
                else:
                    if not parent_bom:
                        # Check no parent
                        parent_todo[parent][4] += 1
                    
                # Stock:    
                stock_net = product.mx_net_qty
                if stock_net < 0:
                    parent_todo[parent][3] += 1

                # Order to produce
                parent_todo[parent][1] += stock_net
                
                # Check negative
                oc_remain = company_pool.mrp_order_line_to_produce(line)
                parent_todo[parent][2] += oc_remain
                
                # -------------------------------------------------------------    
                # Populate halfwork database:
                # -------------------------------------------------------------    
                todo = oc_remain - stock_net
                
                # -----------------------------------------------------------------
                # Halfwork from parent BOM
                # -----------------------------------------------------------------
                for hw in parent_bom.bom_line_ids:
                    halfwork = hw.product_id
                    if halfwork.relative_type != 'half':
                        continue
                    if halfwork not in hws: # halfwork browse obj
                        hws[halfwork] = [
                            0.0, # 0. Needed                            
                            halfwork.mx_net_qty, # 1. Net (after - MRP)
                            {}, # 2. total component
                            # XXX No OF
                            ]
                    # Update total TODO * q. in BOM:
                    hws[halfwork][0] += todo * hw.product_qty
                    # Save total for this bom (parent and halfwork) = key
                    hws[halfwork][2][
                        (parent, halfwork)] = hw.product_qty
                
        # ---------------------------------------------------------------------
        # Clean HW for unload production:
        # ---------------------------------------------------------------------        
        mrp_ids = mrp_pool.search(cr, uid, [
            # State filter:
            ('state', '!=', 'cancel'),                   
            # Period filter (only up not down limit)
            ('date_planned', '>=', reference_date),
            ], context=context)
            
        # Generate MRP total componet report with totals:
        for mrp in mrp_pool.browse(cr, uid, mrp_ids, context=context):
            for sol in mrp.order_line_ids:
                product = sol.product_id                
                qty_maked = sol.product_uom_maked_sync_qty 
                # TODO better use dynamic_bom_line_ids ?
                # check existence
                for hw in product.parent_bom_id.bom_line_ids:
                    halfwork = hw.product_id
                    if halfwork.relative_type != 'half':
                        continue
                    if halfwork not in hws:                        
                        continue # TODO Error not in bom
                    hw_q = qty_maked * hw.product_qty
                    hws[halfwork][1] -= hw_q # - MRP
                    
        # ---------------------------------------------------------------------
        # Prepare report:
        # ---------------------------------------------------------------------
        res = []

        # Empty record
        empty_A = ['' for n in range(0, 6)] # parent 6
        empty_B = ['' for n in range(0, 5)] # halfwork 4
        empty_C = ['' for n in range(0, 6)] # component 6
        
        for parent in sorted(parent_todo):
            record = parent_todo[parent]
            
            # -----------------------------------------------------------------
            #                             BLOCK A:
            # -----------------------------------------------------------------
            # Parent data:
            data_A = [
                parent, # Code
                record[2], # OC
                record[1], # Mag
                record[2] - record[1], # Todo
                record[3], # tot. negative stock (for green-red light)
                record[4], # tot. no bom (for green-red light)
                # TODO
                ]
                
            if not record[0]: # parent bom present:
                res.append(data_A + empty_B + empty_C)
                continue

            parent_first = True
            for hw in record[0].bom_line_ids:
                if parent_first:
                    parent_first = False                    
                else:    
                    data_A = empty_A # reset A

                if not hw.product_id in hws: # hw in the list
                    continue # not in selected list create before
                    
                # ---------------------------------------------------------
                #                           BLOCK B:
                # ---------------------------------------------------------
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
                    ]
                
                hw_first = True
                for cmpt in halfwork.half_bom_ids:
                    if hw_first:
                        hw_first = False
                        data_AB = data_A + data_B
                    else:
                        data_AB = data_A + empty_B
                     
                    # ---------------------------------------------
                    #                  BLOCK C:
                    # ---------------------------------------------
                    
                    proposed = proposed_hw * cmpt.product_qty -\
                        cmpt.product_id.mx_net_qty -\
                        cmpt.product_id.mx_of_in

                    # Add data block directly:
                    res.append(data_AB + [
                        cmpt.product_qty, # total 
                        cmpt.product_id.default_code, # code
                        proposed_hw * cmpt.product_qty,
                        cmpt.product_id.mx_net_qty,
                        cmpt.product_id.mx_of_in,
                        proposed if proposed > 0.0 else 0.0,
                        ])
                            
                if hw_first: # no cmpt data (not in loop)
                    res.append(data_A + data_B + empty_C)
        return res
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
