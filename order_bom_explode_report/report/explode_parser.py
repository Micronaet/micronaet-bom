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
import xlsxwriter
from openerp.osv import fields, osv, expression, orm
from datetime import datetime
from openerp.report import report_sxw
from openerp.report.report_sxw import rml_parse
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)

class MrpProduction(orm.Model):
    """ Model name: MrpProduction
    """    
    _inherit = 'mrp.production'
    

    # Moved here utility for call externally:
    def get_explode_report_object(self, cr, uid, data=None, context=None):
        ''' Search all product elements
            data: 
                mode: use (product), halfwork, component for choose row
                elements
                
                # TODO:
                period: period type week, month
                period: number of period for columns, max 12
                
        '''
        def get_date():
            ''' Get filter selected
            '''
            return datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)
            
        if data is None:
            data = {}

        mode = data.get('mode', 'halfwork')
        first_supplier_id = data.get('first_supplier_id', False)
        with_type_ids = data.get('with_type_ids', [])
        without_type_ids = data.get('without_type_ids', [])
        
        # Add inventory check block:
        for_inventory_delta = data.get('for_inventory_delta', False)
        inventory_delta = {}
        
        # ---------------------------------------------------------------------
        # Utility function embedded:
        # ---------------------------------------------------------------------
        def add_x_item(y_axis, item, category):
            ''' Add new item to record
                y_axis: list of records
                item: bom browse obj
            '''
            product = item.product_id
            default_code = product.default_code or ''            
            if default_code in y_axis:
                return # yet present (for component check)
            y_axis[default_code] = [ # halfworked of component
                # Reset counter for this product    
                # 04/01/2017: change inventory with new
                product.mx_start_qty,
                #product.inventory_start + product.inventory_delta, # inv+delta
                
                0.0, # tcar
                0.0, # tscar
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], # MM  (+ extra per.)
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], # OC  (+ extra per.)
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], # OF  (+ extra per.)
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], # SAL (+ extra per.)
                product, # product or halfworked
                category,
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
        company_pool = self.pool.get('res.company') # for utility
        product_pool = self.pool.get('product.product')
        pick_pool = self.pool.get('stock.picking')
        sale_pool = self.pool.get('sale.order')
        bom_pool = self.pool.get('mrp.bom')
        mrp_pool = self.pool.get('mrp.production')
        
        # Get product BOM dyamic lines (from active order):
        product_data = sale_pool.get_component_in_product_order_open(
            cr, uid, context=context)
        # TODO manage all product for particular category? 
        # SO: filter product in category instead of ordered product    

        # Maybe removed:
        inventory_pos = get_position_season(get_date()) # for inventory mangm.1

        # Load Y axis for report (halfwork or component):
        y_axis = {}
        for product in product_data['product']: # XXX Product ordered for now
            for item in product.dynamic_bom_line_ids: # XXX All Halfworked:
                
                # XXX NOTE: Filter category always in hw not component!
                if with_type_ids and \
                        item.category_id.type_id.id not in with_type_ids:
                    continue # Jump not in category selected
                if without_type_ids and \
                        item.category_id.type_id.id in without_type_ids:
                    continue # Jump not in category selected
                    
                if mode == 'halfwork':
                    if first_supplier_id and \
                            first_supplier_id != \
                                item.product_id.first_supplier_id.id:
                        continue # Jump not supplier present    
                    category = item.category_id.type_id.name if \
                        item.category_id and item.category_id.type_id else \
                            _('No category')
                    add_x_item(y_axis, item, category)
                    
                else: # mode = 'component' 
                    # TODO log halfcomponent with empty list
                    # relative_type = 'half'
                    for component in item.product_id.half_bom_ids:
                        # TODO change category for half component?                        
                        category = ''
                        #category = _('Pipes') if component.product_id.is_pipe \
                        #    else _('Fabric') # TODO correct?
                        add_x_item(y_axis, component, category)

        debug_file.write('\n\nComponent / Halfworked selected:\n%s\n\n'% (
            y_axis.keys()))
        
        # =====================================================================
        # Get parameters for search:
        # =====================================================================
        company_ids = company_pool.search(cr, uid, [])
        company_proxy = company_pool.browse(cr, uid, company_ids)[0]
            
        # Exclude partner list:
        exclude_partner_ids = []

        # Append also this company partner for inventory that need to be excl.    
        # TODO check if is correct the remove of company:
        exclude_partner_ids.append(company_proxy.partner_id.id)
        
        # From date:
        # Period range for documents
        month = datetime.now().month
        year = datetime.now().year
        if month >= 9:
            period_from = '%s-09-01' % year
            mm_from = '%s-09-01' % year # From 01/09 > ALL (so 31/12)
            period_to = '%s-08-31' % (year + 1)
        else:
            period_from = '%s-09-01' % (year - 1) # for OC and OF
            mm_from = '%s-01-01' % year # From 1/1 
            period_to = '%s-08-31' % year

        debug_file.write('\n\nExclude partner list:\n%s\n\n'% (
            exclude_partner_ids, ))

        debug_mm.write(
            'Block|State|Doc.|Origin|Date|Pos.|Prod.|MP|Calc.|MM|OC|OF|Note|Category\n')
        mask = '%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s\n'    

        # =====================================================================
        # 1. LOAD PICKING (CUSTOMER ORDER AND PICK IN)
        # =====================================================================
        block = 'OF, BF, CL, CL prod., CL lav., CL inv.'
        # Keep exclude_partner_ids for CL production esclusion?
        # XXX Note: first for creation of new elements if not present in OC
        
        in_picking_type_ids = []

        # Use textilene company page:
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
                
                if default_code not in y_axis:
                    debug_mm.write(mask % (
                        block, 'NOT USED', pick.name, pick.origin, pick.date,
                        pos, '', # product_code
                        default_code, '', 0, 0, 0,
                        'OF / BF WARNING CODE NOT IN SELECTED LIST (X)',
                        ''
                        )) 
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
                            ''
                            )) 
                        continue

                    pos = get_position_season(line.date_expected)
                    y_axis[default_code][5][pos] += qty # OF block
                    debug_mm.write(mask % (
                        block, 'USED', pick.name, pick.origin, 
                        line.date_expected, pos, '', # product_code                                
                        default_code, '', 0, 0,
                        ('%s' % qty).replace('.', ','), 'OF',
                        ''
                        ))                      
                    continue

                # -------------------------------------------------------------
                #          BF document
                # -------------------------------------------------------------
                # Order delivered so picking in movement
                elif line.state == 'done':
                    date = pick.date or pick.date_done or pick.min_date
                    # 28 gen. 2017 data is now first, after is the last!
                    pos = get_position_season(date)
                
                    # USE order data:
                    # Change for jump year 04/01/2017 (for year change 1/1)
                    #if date > period_to or date < period_from: # extra range
                    if (date < mm_from) or (date > period_to): # extra range
                        debug_mm.write(mask % (
                            block, 'NOT USED', pick.name, pick.origin,
                            date, pos, '', # product_code                                
                            default_code, '', 0, 0, 0,
                            'BF date doc extra range!!: Q.: %s' % qty,
                            ''
                            )) 
                        continue
                    
                    y_axis[default_code][3][pos] += qty # MM block
                    y_axis[default_code][1] += qty # TCAR                    
                    debug_mm.write(mask % (
                        block, 'USED', pick.name, pick.origin, date,
                        pos, '', # product_code                                
                        default_code, '',
                        ('%s' % qty).replace('.', ','), # +MM
                        0, 0, 'BF ADD IN TCAR',
                        ''
                        ))                      
                    continue

        # =====================================================================
        # UNLOAD PICKING (CUSTOMER ORDER PICK OUT) DIRECT SALE OF COMPONENT
        # =====================================================================
        # TODO manage inventory_id > stock.inventory for manual correction 
        block = 'BC PICK OUT' # Direct sale of halfwork
        # XXX Note: no unload MM during BC (only production)
            
        out_picking_type_ids = []
        for item in company_proxy.stock_report_tx_load_out_ids: 
            out_picking_type_ids.append(item.id)
            
        pick_ids = pick_pool.search(cr, uid, [     
            ('picking_type_id', 'in', out_picking_type_ids),
            ('partner_id', 'not in', exclude_partner_ids), # current company
            
            # Only in period # TODO remove if check extra data
            # 04/01/2017 Changed for clean vefore 1/1
            ('date', '>=', mm_from), # XXX 01/09 or 1/1 
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
                        'BC MOVE State not in done (jumped)',
                        ''
                        ))
                    continue    
                    
                # check direct sale:
                if product_code in y_axis: # Component direct:
                    qty = line.product_uom_qty # for direct sale            
                    y_axis[product_code][3][pos] -= qty # MM block  
                    y_axis[product_code][2] -= qty # TSCAR
                    debug_mm.write(mask % (
                        block, 'USED', pick.name, pick.origin,
                        pick.date, pos, '', product_code, # Prod is MP
                        '', ('%s' % -qty).replace('.', ','), # MM
                        0, 0, 'BC MOVE Direct sale of component (ADD IN TSCAR)',
                        ''
                        ))
                    continue    
                
        # =====================================================================
        #                  CUSTMER ORDER TO PRODUCE (NOT DELIVERED)
        # =====================================================================
        block = 'OC (not delivered)'
        # XXX Note: used only for manage OC remain: 
        #    OC - B if B > Del.
        #    OC - Del if B < Del.
        
        order_ids = company_pool.mrp_domain_sale_order_line(
            cr, uid, context=context)
            
        for order in sale_pool.browse(cr, uid, order_ids, context=context):
            # Search in order line:
            for line in order.order_line:                
                # FC order no deadline (use date)
                #datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)) 
                product = line.product_id # readability
                product_code = line.product_id.default_code
                date = line.date_deadline or order.date_order
                pos = get_position_season(date)
                
                # OC exclude no parcels product:                
                if product.exclude_parcels:
                    debug_mm.write(mask % (
                        block, 'NOT USED', order.name, '', date, pos, '', #code
                        product_code, # Direct component
                        '', 0, # +MM
                        0, # XXX keep 0 (-OC)
                        0, 'OC NO PARCELS PRODUCT',
                        ''
                        ))                      
                    continue     

                (remain, not_delivered) = \
                    company_pool.mrp_order_line_to_produce(line)

                # --------------------------------
                # OC direct halfwork or component:
                # --------------------------------
                # Explode HW subcomponent for report 2
                if mode != 'halfwork': 
                    for comp in product.half_bom_ids:
                        comp_code = comp.product_id.default_code
                        if comp_code not in y_axis: # OC out item (no prod.):
                            # TODO log component not used
                            continue
                        comp_remain = remain * comp.product_qty
                        y_axis[comp_code][4][pos] -= comp_remain # OC
                        debug_mm.write(mask % (
                            block, 'USED', order.name, '', date, pos, 
                            product_code, # Code
                            comp_code, # component
                            '', 0, # +MM
                            ('%s' % comp_remain).replace('.', ','),#-OC
                            0, 'OC DIRECT SALE HW SO COMPONENT UNLOAD',
                            comp.category_id.name if comp.category_id else\
                                'NO CATEGORY',
                            ))
                        # go ahead for download component    

                # Direct sale hw or component:
                if product_code in y_axis: # HW or component direct:
                    y_axis[product_code][4][pos] -= remain # OC block
                    debug_mm.write(mask % (
                        block, 'USED', order.name, '', date, pos, '', # code
                        product_code, # Direct component
                        '', 0, # +MM
                        ('%s' % remain).replace('.', ','), # -OC
                        0, 'OC DIRECT SALE HALFWORK OR COMPONENT',
                        ''
                        ))                      
                    continue                          
                 
                if not len(product.dynamic_bom_line_ids): # no bom
                    debug_mm.write(mask % (
                        block, 'NOT USED', order.name, '', date, pos,
                        product_code, '', # Original product
                        '', 0, # +MM
                        0, # -OC
                        0, 'OC PRODUCT WITHOUT BOM, Q.: %s' % remain,
                        ''
                        ))                      
                    continue

                # TODO error for negative?
                if remain <= 0:
                    debug_mm.write(mask % (
                        block, 'NOT USED', order.name, '', date, pos,
                        product_code, '', # MP
                        '', 0, # +MM
                        0, 0, 'OC ALL DELIVERED OR NEGATIVE DELIVER',
                        ''
                        ))  
                    continue
                
                # USE order data:
                # Note: Remain period_from instead of mm_from exclude extra 
                # period order always 1/9
                if date > period_to or date < period_from: # extra range
                    debug_mm.write(mask % (
                        block, 'NOT USED', order.name, '', date, pos,
                        product_code, '', # MP
                        '', 0, # +MM
                        0, 0, 'OC EXTRA RANGE, qty: %s' % remain,
                        ''
                        ))                      
                    continue

                # -----------------------------------
                # OC Halfworked or Component explode:
                # -----------------------------------
                for item in product.dynamic_bom_line_ids:
                    item_code = item.product_id.default_code
                    item_remain = remain * item.product_qty
                    
                    if mode == 'halfwork':
                        if item_code in y_axis: # OC out item (no prod.):
                            y_axis[item_code][4][pos] -= item_remain # OC block
                            debug_mm.write(mask % (
                                block, 'USED', order.name, '', date, pos, 
                                product_code, # code
                                item_code, # MP
                                '', 0, # +MM
                                ('%s' % item_remain).replace('.', ','), # -OC
                                0, 'OC HALFWORKED REMAIN',
                                item.category_id.name if item.category_id \
                                    else 'NO CATEGORY',
                                ))                      
                        # else: TODO log not used        
                    else: # mode = 'component'
                        for comp in item.product_id.half_bom_ids:
                            comp_code = comp.product_id.default_code
                            if comp_code not in y_axis: # OC out item (no prod.):
                                debug_mm.write(mask % (
                                    block, 'NOT USED', order.name, '', date, pos, 
                                    item_code, # Code
                                    comp_code, # component
                                    '', 0, # +MM
                                    ('%s' % comp_remain).replace('.', ','),#-OC
                                    0, 'COMPONENT NOT IN FILTER X LIST' ,
                                    comp.category_id.name if comp.category_id\
                                        else 'NO CATEGORY',
                                    ))
                                continue
                            comp_remain = item_remain * comp.product_qty
                            y_axis[comp_code][4][pos] -= comp_remain # OC
                            debug_mm.write(mask % (
                                block, 'USED', order.name, '', date, pos, 
                                item_code, # Code
                                comp_code, # component
                                '', 0, # +MM
                                ('%s' % comp_remain).replace('.', ','),#-OC
                                0, 'OC COMPONENT REMAIN',
                                comp.category_id.name if comp.category_id else\
                                    'NO CATEGORY',
                                ))
                        continue                
                    
        # =====================================================================
        #                  UNLOAD FOR PRODUCTION MRP ORDER
        # =====================================================================
        block = 'MRP (unload component prod.)'
        # XXX Note: used only for manage OC remain: 
        
        if mode == 'halfwork': # only half explode MRP (comp > lavoration)
            mrp_ids = mrp_pool.search(cr, uid, [        
                # State filter:
                ('state', '!=', 'cancel'), # TODO correct? for unload element?
                
                # Period filter:
                # 04/01/2017 MRP from 1/9 or 1/1 depend on change year
                ('date_planned', '>=', mm_from), # 1/9 or 1/1
                ('date_planned', '<=', period_to), 
                
                # No customer exclude filter
                ])
            
            for order in mrp_pool.browse(cr, uid, mrp_ids, context=context):
                date = order.date_planned
                
                # Search in order line:
                for line in order.order_line_ids:
                    product = line.product_id # readability
                    product_code = line.product_id.default_code
                    pos = get_position_season(date)                                
                    qty = line.product_uom_maked_sync_qty

                    # XXX No direct production (use lavorat. CL / CL for this):
                    
                    if not len(product.dynamic_bom_line_ids): # no bom
                        debug_mm.write(mask % (
                            block, 'NOT USED', order.name, '', date, pos,
                            product_code, '', # Original product
                            '', 0, # +MM
                            0, # -OC
                            0, 'MRP PRODUCT WITHOUT BOM, Q.: %s' % qty,
                            '',
                            ))                      
                        continue

                    # --------------------
                    # Search in component:
                    # --------------------
                    for comp in product.dynamic_bom_line_ids:
                        comp_code = comp.product_id.default_code
                        comp_qty = qty * comp.product_qty 

                        # Check placehoder:
                        if comp.product_id.bom_placeholder:#TODO bom_alternative
                            debug_mm.write(mask % (
                                block, 'NOT USED', order.name, '', date, pos, 
                                product_code,
                                comp_code, # MP
                                '', ('%s' % -comp_qty).replace('.', ','),
                                0, 0, 'MRP PRESENTE UN [DA ASSEGNARE]',
                                comp.category_id.name if comp.category_id else\
                                    'NO CATEGORY',
                                ))                       
                            continue
                            
                        if comp_code in y_axis: # OC out component (no prod.):
                            y_axis[comp_code][3][pos] -= comp_qty # MM block
                            y_axis[comp_code][2] -= comp_qty #TSCAR for MRP
                            debug_mm.write(mask % (
                                block, 'USED', order.name, '', date, pos, 
                                product_code,
                                comp_code, # MP
                                '', ('%s' % -comp_qty).replace('.', ','), # -MM
                                0, 0, 'MRP COMPONENT UNLOAD (ADD in TSCAR)',
                                comp.category_id.name if comp.category_id else\
                                    'NO CATEGORY',
                                ))                       
                            continue
                        else:
                            debug_mm.write(mask % (
                                block, 'NOT USED', order.name, '', date, pos, 
                                product_code,
                                comp_code, # MP
                                '', ('%s' % -comp_qty).replace('.', ','), # -MM
                                0, 0, 'MRP COMPONENT NOT IN LIST',
                                comp.category_id.name if comp.category_id else\
                                    'NO CATEGORY',
                                ))  
                            continue                         

        # ---------------------------------------------------------------------
        # Prepare data for report:
        # ---------------------------------------------------------------------
        res = []
        self.jumped = []
    
        # TODO textilene sort block:
        # (y_axis[code][8], code[0:3], code[6:12], code[3:6])
        for key in sorted(y_axis, key=lambda code: (y_axis[code][8], code)):
            # -----------------------------------------------------------------    
            # Normal report block:
            # -----------------------------------------------------------------    
            current = y_axis[key] # readability:
            product = current[7]

            total = 0.0 # INV 0.0
            
            # XXX NOTE: INV now is 31/12 next put Sept. (old information)
            # inv_pos = 3 # December # TODO never use this!!!
            inv_pos = 0 # September (always append here inventory)
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
                    # TODO remove from TCAR inventory!!!
                    #current[1] -= round(current[0], 0) # TCAR                
                    total += round(current[0], 0) # Add inv.

                total += round(
                    current[3][i] + current[4][i] + current[5][i], 0)
                current[6][i] = int(total)
                
            # -----------------------------------------------------------------    
            # Inventory managenent block:
            # -----------------------------------------------------------------  
            # XXX maybe remove:  
            if for_inventory_delta and \
                    product.default_code not in inventory_delta:
                inventory_delta[product.default_code] = (
                    product.inventory_start, # 0. INV
                    sum(current[4][0: inventory_pos + 1]), # 1. Current OC
                    sum(current[5][0: inventory_pos + 1]), # 2. Current OF
                    current[6][inventory_pos], # 3. Current SAL
                    product.inventory_delta, # 4. Delta
                    )

            # Append progress totals:
            if not jumped:
                res.append(current)

        # Return depend on request inventory or report        
        if for_inventory_delta:
            return inventory_delta
        else:    
            return res    
    
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
                mode: use (product), halfwork, component for choose row
                elements
                
                # TODO:
                period: period type week, month
                period: number of period for columns, max 12
                
        '''
        # Readability:    
        cr = self.cr
        uid = self.uid
        context = {}
        
        return self.pool.get('mrp.production').get_explode_report_object(
            cr, uid, data=data, context=context)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
