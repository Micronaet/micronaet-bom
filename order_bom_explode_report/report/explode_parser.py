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
import erppeek
import pickle
from datetime import datetime
from openerp.report import report_sxw
from openerp.report.report_sxw import rml_parse
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)

class Parser(report_sxw.rml_parse):
    counters = {}
    headers = {}
    
    def __init__(self, cr, uid, name, context):        
        super(Parser, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'get_object': self.get_object,
            'get_jumped': self.get_jumped,
            'get_filter': self.get_filter,
            'get_date': self.get_date,
            })

    def get_jumped(self, ):
        ''' Get filter selected
        '''
        return self.jumped

    def get_date(self, ):
        ''' Get filter selected
        '''
        return datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)

    def get_filter(self, data):
        ''' Get filter selected
        '''
        data = data or {}
        return data.get('partner_name', '')
    
    def get_object(self, data):
        ''' Search all product elements
            data: 
                mode: use (product), component, subcomponent for choose row
                elements
                # TODO:
                period: period type week, month
                period: number of period for columns, max 12
        '''
        # Readability:    
        cr = self.cr
        uid = self.uid
        context = {}
        if data is None:
            data = {}
        
        # ---------------------------------------------------------------------
        # Utility function embedded:
        # ---------------------------------------------------------------------
        def add_product_component(products, component, data=None):
            ''' Add new component to record
                products: list of records
                component: browse obj
            '''
            product = component.product_id
            products[product.default_code] = [
                # Reset counter for this product    
                product.inventory_start or 0.0, # inv
                0.0, # tcar
                0.0, # tscar
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], # MM
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], # OC
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], # OF
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], # SAL
                product,
                ]
            return    
            
        def get_position_season(date):
            ''' Return position in array for correct season month:
            '''
            if not date:
                _logger.error('Date not found')
                return False
            month = int(date[5:7])
            if month >= 9: # september = 0
                return month - 9
            # january = 4    
            return month + 3    
        
        # Debug files:
        debug_f = '/home/administrator/photo/log/explode_status.txt'
        debug_f_mm = '/home/administrator/photo/log/explode_mm.csv'
        debug_file = open(debug_f, 'w')
        debug_mm = open(debug_f_mm, 'w')

        # pool used:
        product_pool = self.pool.get('product.product')
        pick_pool = self.pool.get('stock.picking')
        sale_pool = self.pool.get('sale.order')
        bom_pool = self.pool.get('mrp.bom')
        mrp_pool = self.pool.get('mrp.production')
        
        product_data = sale_pool.get_component_in_product_order_open(
            cr, uid, context=context)

        products = {}

        for product in product_data['product']:
            for component in product.dynamic_bom_line_ids:
                add_product_component(products, component)

        debug_file.write('\n\nComponent selected:\n%s\n\n'% (
            products.keys()))
        
        # =====================================================================
        # Get parameters for search:
        # =====================================================================
        company_pool = self.pool.get('res.company')
        company_ids = company_pool.search(cr, uid, [])
        company_proxy = company_pool.browse(cr, uid, company_ids)[0]
            
        # Exclude partner list:
        exclude_partner_ids = []

        # Append also this company partner for inventory that need to be excl.    
        exclude_partner_ids.append(company_proxy.partner_id.id)
        
        # From date:
        # Period range for documents
        month = datetime.now().month
        year = datetime.now().year
        if month >= 9:
            period_from = '%s-09-01' % year
            period_to = '%s-08-31' % (year + 1)
        else:
            period_from = '%s-09-01' % (year - 1)
            period_to = '%s-08-31' % year
            
        debug_file.write('\n\nExclude partner list:\n%s\n\n'% (
            exclude_partner_ids, ))

        debug_mm.write(
            'Block|State|Doc.|Origin|Date|Pos.|Prod.|MP|Calc.|MM|OC|OF|Note\n')
        mask = '%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s\n'    

        # =====================================================================
        # 1. LOAD PICKING (CUSTOMER ORDER AND PICK IN )
        # =====================================================================
        block = 'OF and BF'
        # XXX Note: first for creation of new elements if not present in OC
        
        in_picking_type_ids = []
        # XXX Note: use textilene data:
        for item in company_proxy.stock_report_tx_load_in_ids:
            in_picking_type_ids.append(item.id)
            
        pick_ids = pick_pool.search(cr, uid, [     
            ('picking_type_id', 'in', in_picking_type_ids),            
            ('partner_id', 'not in', exclude_partner_ids),            
            # check data date (old method
            #('date', '>=', from_date), # XXX correct for virtual?
            #('date', '<=', to_date),
            # TODO state filter
            ])
            
        for pick in pick_pool.browse(cr, uid, pick_ids, context=context):
            pos = get_position_season(pick.date) # for done cols  (min_date?)
            for line in pick.move_lines:
                default_code = line.product_id.default_code                              
                qty = line.product_uom_qty
                
                if default_code not in products:
                    debug_mm.write(mask % (
                        block, 'NOT USED', pick.name, pick.origin, pick.date,
                        pos, '', # product_code
                        default_code, '', 0, 0, 0,
                        'OF / BF Warn. Code not in component',
                        )) 
                    # TODO create record if component or halfwork!!!!!!!!!!!!!!
                    continue

                # -------------------------------------------------------------
                #          OF document
                # -------------------------------------------------------------
                # Order not current delivered:
                if line.state == 'assigned': # virtual
                    # USE deadline data in the period:
                    if line.date_expected > period_to or \
                            line.date_expected < period_from: # extra range
                        debug_mm.write(mask % (
                            block, 'NOT USED', pick.name, pick.origin,
                            line.date_expected, '', # POS
                            '', # product_code                                
                            default_code, '', 0, 0, 0,
                            'OF date expected extra range!: Q.: %s' % qty,
                            )) 
                        continue

                    pos = get_position_season(line.date_expected)
                    products[default_code][5][pos] += qty # OF block
                    debug_mm.write(mask % (
                        block, 'USED', pick.name, pick.origin, line.date_expected,
                        pos, '', # product_code                                
                        default_code, '', 0, 0,
                        ('%s' % qty).replace('.', ','), 'OF',
                        ))                      
                    continue

                # -------------------------------------------------------------
                #          BF document
                # -------------------------------------------------------------
                # Order delivered so picking in movement
                elif line.state == 'done':
                    date = pick.date_done or pick.min_date or pick.date
                    pos = get_position_season(date)
                
                    # USE order data:
                    if date > period_to or date < period_from: # extra range
                        debug_mm.write(mask % (
                            block, 'NOT USED', pick.name, pick.origin,
                            date, pos, '', # product_code                                
                            default_code, '', 0, 0, 0,
                            'BF date doc extra range!!: Q.: %s' % qty,
                            )) 
                        continue
                    
                    products[default_code][3][pos] += qty # MM block
                    products[default_code][1] += qty # TCAR                    
                    debug_mm.write(mask % (
                        block, 'USED', pick.name, pick.origin, date,
                        pos, '', # product_code                                
                        default_code, '',
                        ('%s' % qty).replace('.', ','), # +MM
                        0, 0, 'BF ADD IN TCAR',
                        ))                      
                    continue

        # =====================================================================
        # UNLOAD PICKING (CUSTOMER ORDER PICK OUT) DIRECT SALE OF COMPONENT
        # =====================================================================
        block = 'BC PICK OUT' # Direct sale of halfwork
        # XXX Note: no unload MM during BC (only production)
            
        out_picking_type_ids = []
        for item in company_proxy.stock_report_tx_load_out_ids: 
            out_picking_type_ids.append(item.id)
            
        pick_ids = pick_pool.search(cr, uid, [     
            ('picking_type_id', 'in', out_picking_type_ids),
            ('partner_id', 'not in', exclude_partner_ids), # current company
            
            # Only in period # TODO remove if check extra data
            ('date', '>=', period_from), 
            ('date', '<=', period_to), 
            ])
            
        for pick in pick_pool.browse(cr, uid, pick_ids):
            pos = get_position_season(pick.date) # cols  (min_date?)
            # TODO no check for period range
            for line in pick.move_lines:               
                product_code = line.product_id.default_code
                product = line.product_id                
                if line.state != 'done':
                    debug_mm.write(mask % (
                        block, 'NOT USED', pick.name, pick.origin, pick.date, 
                        pos, product_code, '', '', 0, 0, 0,
                        'State not in done (jumped)',
                        ))
                    continue    
                    
                # check direct sale:
                if product_code in products: # Component direct:
                    qty = line.product_uom_qty # for direct sale            
                    products[product_code][3][pos] -= qty # MM block  
                    products[product_code][2] -= qty # TSCAR
                    debug_mm.write(mask % (
                        block, 'USED', pick.name, pick.origin,
                        pick.date, pos, '', product_code, # Prod is MP
                        '', ('%s' % -qty).replace('.', ','), # MM
                        0, 0, 'Direct sale of component (ADD IN TSCAR)',
                        ))
                    continue    
                
        # =====================================================================
        #                  UNLOAD ORDER TO PRODUCE (NON DELIVERED)
        # =====================================================================
        block = 'OC (not delivered)'
        # XXX Note: used only for manage OC remain: 
        #    OC - B if B > Del.
        #    OC - Del if B < Del.
        
        order_ids = sale_pool.search(cr, uid, [
            ('state', 'not in', ('cancel', 'send', 'draft')),
            ('pricelist_order', '=', False),
            ('partner_id', 'not in', exclude_partner_ids),
            ('mx_closed', '=', False), # Only open orders (not all MRP after)
            # Also forecasted order
            # TODO filter date?            
            # TODO filter products?
            ])
            
        for order in sale_pool.browse(cr, uid, order_ids, context=context):
            # Search in order line:
            for line in order.order_line:                
                # FC order no deadline (use date)
                #datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)) 
                product_code = line.product_id.default_code
                date = line.date_deadline or order.date_order
                pos = get_position_season(date)
                
                # TODO manage forecast order ...     
                # Check remain to produce
                if line.product_uom_maked_sync_qty >= line.delivered_qty:
                    remain = \
                        line.product_uom_qty - line.product_uom_maked_sync_qty
                else:    
                    remain = line.product_uom_qty - line.delivered_qty

                # OC direct component:
                if product_code in products:
                    products[product_code][4][pos] -= remain # OC block
                    debug_mm.write(mask % (
                        block, 'USED', order.name, '', date, pos, '', # code
                        product_code, # Direct component
                        '', 0, # +MM
                        ('%s' % remain).replace('.', ','), # -OC
                        0, 'OC DIRECT COMPONENT AS PRODUCT',
                        ))                      
                    continue                    

                if not len(product.dynamic_bom_line_ids): # no bom
                    debug_mm.write(mask % (
                        block, 'NOT USED', order.name, '', date, pos,
                        product_code, '', # Original product
                        '', 0, # +MM
                        0, # -OC
                        0, 'PRODUCT WITHOUT BOM, Q.: %s' % remain,
                        ))                      
                    continue

                # TODO error for negative?
                if remain <= 0:
                    debug_mm.write(mask % (
                        block, 'NOT USED', order.name, '', date, pos,
                        product_code, '', # MP
                        '', 0, # +MM
                        0, 0, 'ALL DELIVERED',
                        ))  
                    continue
                
                # USE order data:
                if date > period_to or date < period_from: # extra range
                    debug_mm.write(mask % (
                        block, 'NOT USED', order.name, '', date, pos,
                        product_code, '', # MP
                        '', 0, # +MM
                        0, 0, 'EXTRA RANGE, qty: %s' % remain,
                        ))                      
                    continue

                # --------------------
                # Search in component:
                # --------------------
                for comp in line.dynamic_bom_line_ids:
                    comp_code = comp.product_id.default_code
                    if comp_code in products: # OC out component (no prod.):
                        comp_remain = remain * comp.product_qty
                        products[comp_code][4][pos] -= comp_remain # OC block
                        debug_mm.write(mask % (
                            block, 'USED', order.name, '', date, pos, '', # code
                            comp_code, # MP
                            '', 0, # +MM
                            ('%s' % comp_remain).replace('.', ','), # -OC
                            0, 'OC COMPONENT REMAIN',
                            ))                      
                        continue                    
                    
        # =====================================================================
        #                  UNLOAD FOR PRODUCTION MRP ORDER
        # =====================================================================
        block = 'MRP (unload component prod.)'
        # XXX Note: used only for manage OC remain: 
        
        mrp_ids = sale_pool.search(cr, uid, [
            # State filter:
            ('state', '!=', 'cancel'),
            
            # Period filter:
            ('date', '>=', period_from), 
            ('date', '<=', period_to), 
            ])
            
        for order in mrp_pool.browse(cr, uid, mrp_ids, context=context):
            date = order.date_planned
            
            # Search in order line:
            for line in order.order_line_ids:                
                product = line.product_id # readability
                product_code = line.product_id.default_code
                pos = get_position_season(date)                                
                qty = line.product_uom_maked_sync_qty

                # XXX No direct production:
                
                if not len(product.dynamic_bom_line_ids): # no bom
                    debug_mm.write(mask % (
                        block, 'NOT USED', order.name, '', date, pos,
                        product_code, '', # Original product
                        '', 0, # +MM
                        0, # -OC
                        0, 'MRP PRODUCT WITHOUT BOM, Q.: %s' % qty,
                        ))                      
                    continue

                # --------------------
                # Search in component:
                # --------------------
                for comp in product.dynamic_bom_line_ids:
                    comp_code = comp.product_id.default_code
                    if comp_code in products: # OC out component (no prod.):
                        comp_qty = qty * comp.product_qty 
                        products[comp_code][3][pos] -= comp_qty # MM block
                        products[product_code][2] -= comp_qty #TSCAR XXX also mrp?
                        debug_mm.write(mask % (
                            block, 'USED', order.name, '', date, pos, '',
                            comp_code, # MP
                            '', ('%s' % -comp_qty).replace('.', ','), # -MM
                            0, 'MRP COMPONENT B',
                            ))                      
                        continue                    

        # ---------------------------------------------------------------------
        # Prepare data for report:
        # ---------------------------------------------------------------------
        res = []
        self.jumped = []
        for key in sorted(products, key=lambda products: '%s%s%s' % (
                products[0:3] or ' ' * 3,
                products[6:12] or ' ' * 6,
                products[3:6] or ' ' * 3,
                )):
            current = products[key] # readability:
            total = 0.0 # INV 0.0
            
            # NOTE: INV now is 31/12 next put Sept.
            # inv_pos = 3 # December
            inv_pos = 0 # September
            jumped = False
            for i in range(0, 12):
                #if i == inv_pos:
                #    current[3][i] += round(current[0], 0) # add inv.
                current[3][i] = int(round(current[3][i], 0))
                current[4][i] = int(round(current[4][i], 0))
                current[5][i] = int(round(current[5][i], 0))
                
                # Empty block test:
                if not(any(current[3]) or any(current[4]) or \
                        any(current[5]) or current[0]> 0.0):
                    #_logger.warning('Jumped: %s %s %s' % current
                    self.jumped.append(current[7]) # product proxy
                    jumped = True
                    continue    
                
                if i == inv_pos:
                #    TODO remove from TCAR inventory!!!
                    #current[1] -= round(current[0], 0) # TCAR                
                    total += round(current[0], 0) # Add inv.

                total += round(
                    current[3][i] + current[4][i] + current[5][i], 0)
                current[6][i] = int(total)

            # Append progress totals:
            if not jumped:
                res.append(current)
        return res

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
