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
import xlsxwriter
import openerp.netsvc as netsvc
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _
from openerp.report import report_sxw
from openerp.report.report_sxw import rml_parse
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp.osv import fields, osv, expression, orm
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)

type_i18n = {
    'industrial': 'COSTI INDUSTRIALI',
    'work': 'MANODOPERA',
    }    

# -----------------------------------------------------------------------------
#                      UTILITY (TODO move in a module or class?):
# -----------------------------------------------------------------------------
def industrial_index_get_text(index):
    ''' Convert all index value in string format
    '''
    index_total = sum(index.values())
    res = ''
    for key, value in index.iteritems():
        res += '%s: %6.3f / %6.3f > %s%%\r\n' % (
            type_i18n.get(key, '?'), 
            value, index_total,
            ('%6.3f' % (100.0 * value / index_total, )) if \
                index_total else 'ERRORE!',
            )
    return res
    
def load_subelements_price(self, res, mode, item, product, hw=False):
    ''' Load list in all seller pricelist return min and max value
    '''
    min_value = 0.0
    max_value = 0.0
    
    record = [
        mode, item, [], 
        False, # not used here
        ]
        
    # TODO manage as pipe?
    for seller in product.seller_ids:
         for pricelist in seller.pricelist_ids:
             if not pricelist.is_active:
                 continue                         
             total = pricelist.price * item.product_qty
             record[2].append((
                 seller.name.name,
                 '%10.5f' % pricelist.price,
                 pricelist.date_quotation or '???',
                 '%10.5f' % total,
                 hw,
                 ))
             if not min_value or total < min_value:
                 min_value = total
             if total > max_value:
                 max_value = total
                 
    # Update min and max value:             
    self.min += min_value
    self.max += max_value
    res.append(record)
    return record[2] # error test for check price present

def get_pricelist(product, cmpt_q, date_ref):
    ''' Return:
        min, max, all pricelist for this product
        active price, reference >= passed
    '''
    res = [
        False, # Min
        0.0, # Max
        [], # Price list
        ]
        
    for seller in product.seller_ids:
         for pricelist in seller.pricelist_ids:
             # no inactive price XXX remove this filter?
             if not pricelist.is_active: # no inactive
                 continue            
                       
             # Take only period date:
             if pricelist.date_quotation and \
                    pricelist.date_quotation <= date_ref:
                 continue
             
             date_quotation = pricelist.date_quotation
             price = pricelist.price
             total = cmpt_q * price
                                              
             # XXX Used:    ???
             res[2].append((
                 seller.name, # Supplier browse
                 price, # Unit price
                 date_quotation or '???', # Date
                 total, # Subtotal
                 ))
             
             # Save min or max price:    
             if not res[0] or total < res[0]:
                 res[0] = total
             if total > res[1]:
                 res[1] = total
    return res             

class ProductProduct(orm.Model):
    """ Model name: ProductProduct add utility for report
    """
    
    _inherit = 'product.product'
    
    # -------------------------------------------------------------------------
    # Button event:
    # -------------------------------------------------------------------------
    def open_single_report(self, cr, uid, ids, context=None):
        ''' Return single report
        '''
        datas = {}
        datas['wizard'] = True # started from wizard
        datas['active_ids'] = ids
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'industrial_cost_bom_report', 
            'datas': datas,
            #'context': context,
            }

    def open_multi_report(self, cr, uid, ids, context=None):
        ''' Return multi report
        '''
        datas = {}
        datas['wizard'] = True # started from wizard
        datas['active_ids'] = False
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'industrial_cost_bom_report', 
            'datas': datas,
            #'context': context,
            }

    def open_xls_report(self, cr, uid, ids, context=None):
        ''' Return xls report
        '''
        # Utility:
        def xls_write_row(WS, row, row_data, format_cell):
            ''' Print line in XLS file            
            '''
            ''' Write line in excel file
            '''
            col = 0
            for item in row_data:
                WS.write(row, col, item, format_cell)
                col += 1
            return True
            
        datas = {}
        datas['wizard'] = True # started from wizard
        datas['active_ids'] = False
        
        xls_filename = '/tmp/bom_report.xlsx'
        _logger.info('Start export BOM cost on %s' % xls_filename)
        
        # Open file and write header
        WB = xlsxwriter.Workbook(xls_filename)
        WS = WB.add_worksheet('Product')

        # Format:
        format_title = WB.add_format({
            'bold': True, 
            'font_color': 'black',
            'font_name': 'Arial',
            'font_size': 10,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': 'gray',
            'border': 1,
            'text_wrap': True,
            })

        format_text = WB.add_format({
            'font_name': 'Arial',
            #'align': 'left',
            'font_size': 9,
            'border': 1,
            })

        format_white = WB.add_format({
            'font_name': 'Arial',
            'font_size': 9,
            'align': 'right',
            'bg_color': 'white',
            'border': 1,
            'num_format': '0.00',
            })        
        
        # ---------------------------------------------------------------------
        # Get database of industrial cost:
        # ---------------------------------------------------------------------
        cost_db = {}
        
        cost_pool = self.pool.get('mrp.bom.industrial.cost')
        cost_ids = cost_pool.search(cr, uid, [], order='name', context=context)
        i = 0
        for cost in cost_pool.browse(cr, uid, cost_ids, context=context):
            cost_db[cost.name] = i # position in Excel file
            i += 1
  
        WS.set_column('A:A', 10)
        WS.set_column('B:B', 35)
        WS.set_column('C:AX', 10)
        
        header = [
            _('Codice'), 
            _('Descrizione'), 
            _('Min'), 
            _('Max'), 
            _('Prezzo non presente')]
        header.extend(sorted(cost_db, key=lambda x: cost_db[x]))
        xls_write_row(WS, 0, header, format_title)
        
        # ---------------------------------------------------------------------
        # Get product cost information
        # ---------------------------------------------------------------------
        row = 0
        for product in self._report_industrial_get_objects(
                cr, uid, data=datas, context=context):
            row += 1
            not_details = False

            industrial_cost = [0.0 for col in range(0, len(cost_db))]
            for mode, item, details, time_qty in \
                    self._report_industrial_get_details(
                        cr, uid, product, context=context):
                if mode in ('C', 'S'):
                    if not details: # Check if not details 
                        not_details = True
                elif mode == 'T':
                    # Industrial cost
                    if time_qty:                        
                        industrial_cost[cost_db[item.cost_id.name]] = \
                            '%s (T. %s)' % (details, time_qty)
                    else:        
                        industrial_cost[cost_db[item.cost_id.name]] = details
                else:
                    pass # Heder row

            cost_min = self._report_industrial_get_totals('min')
            cost_max = self._report_industrial_get_totals('max')
            
            # -----------------------------------------------------------------
            # Print XLS row data:
            # -----------------------------------------------------------------
            row_data = [
                product.default_code, 
                product.name, 
                cost_min, 
                cost_max,
                'X' if not_details else ''
                ]

            row_data.extend(industrial_cost)
            xls_write_row(WS, row, row_data, format_text)
            
        _logger.info('End export BOM cost on %s' % xls_filename)
        WB.close()

        attachment_pool = self.pool.get('ir.attachment')
        b64 = open(xls_filename, 'rb').read().encode('base64')
        attachment_id = attachment_pool.create(cr, uid, {
            'name': 'BOM industrial cost',
            'datas_fname': 'bom_industrial_cost_report.xlsx',
            'type': 'binary',
            'datas': b64,
            'partner_id': 1,
            'res_model':'res.partner',
            'res_id': 1,
            }, context=context)
        
        return {
            'type' : 'ir.actions.act_url',
            'url': '/web/binary/saveas?model=ir.attachment&field=datas&'
                'filename_field=datas_fname&id=%s' % attachment_id,
            'target': 'self',
            }   
            
    # -------------------------------------------------------------------------
    # Report utility:
    # -------------------------------------------------------------------------
    def _report_industrial_get_objects(self, cr, uid, data=None, context=None):
        ''' Return single report or list of selected bom 
            Used in report and in XLSX extract files
        '''        
        # Readability:
        if data is None:
            data = {}

        if not data.get('wizard', False):
            raise osv.except_osv(
                _('Access error'), 
                _('No right to print BOM'),
                )
                
        # Pool used:    
        product_pool = self.pool.get('product.product')
        
        active_ids = data.get('active_ids', False)            
        if not active_ids:
            active_ids = self.search(cr, uid, [
                ('bom_selection', '=', True),
                ], context=context)
        objects = self.browse(cr, uid, active_ids, context=context)
           
        #return objects #sorted(objects, key=lambda o: o.default_code)
        return sorted(objects, key=lambda o: o.default_code)

    def _report_industrial_get_details(self, cr, uid, product, context=None):
        ''' Create detail row
        '''        
        # Pool used:           
        product_pool = self.pool.get('product.product')        
        if context is None:
            context = {}

        # ---------------------------------------------------------------------
        # Load component list (and subcomponent for HW):
        # ---------------------------------------------------------------------
        res = []
        # Min / Max totals:
        self.min = 0.0
        self.max = 0.0
        error = False # for write in product
        for item in product.dynamic_bom_line_ids:
            component = item.product_id
            half_bom_ids = component.half_bom_ids # if half component
            if half_bom_ids: # HW component
                for cmpt in half_bom_ids:
                    test = load_subelements_price(
                        self, res, 'S', cmpt, cmpt.product_id, 
                        item.product_id.default_code,
                        )
                    if not test:
                        error = True

            else: # not HW component
                test = load_subelements_price(
                    self, res, 'C', item, item.product_id)
                if not test:
                    error = True

        # ---------------------------------------------------------------------
        # Extra data end report:
        # ---------------------------------------------------------------------
        # Append totals:
        last_type = False
        supplement_cost = sorted(
            product_pool.get_cost_industrial_for_product(
                cr, uid, [product.id], context=context).iteritems(),
            key=lambda x: (x[0].type, x[0].name),
            )
                    
        index = {
            _('Componenti'): self.max, # used max:
            }            
        for cost, item in supplement_cost:
            if last_type != cost.type:
                last_type = cost.type
                # Add header (change every category break level):
                res.append(('H', type_i18n.get(last_type, '?'), False, 
                    False, # no used
                    ))
                index[cost.type] = 0.0
                
            # 2 case: with product or use unit_cost    
            if item.product_id: # use item price
                value = item.qty * item.last_cost                
                time_qty = False
            else:
                value = item.qty * cost.unit_cost                     
                time_qty = item.qty
                
            res.append(('T', item or '???', value, time_qty))
            self.min += value
            self.max += value
            index[cost.type] += value # for index calc

        # Save margin parameters:        
        self.margin_a = \
            self.max * product.company_id.industrial_margin_a / 100.0 
        self.margin_b = \
            self.max * product.company_id.industrial_margin_b / 100.0 
            
        # Write status in row:    
        self.index = industrial_index_get_text(index)
        if context.get('update_record', True): # XXX always true for now:
            product_pool.write(cr, uid, product.id, {
                'from_industrial': self.min,
                'to_industrial': self.max,
                'industrial_missed': error,
                'industrial_index': self.index,
                }, context=context)
        return res

    def _report_industrial_get_totals(self, mode):
        ''' Total value (min or max)
        '''    
        if mode == 'min':
            return self.min
        elif mode == 'index':
            return self.index,    
        elif mode == 'margin_a':
            return self.margin_a,    
        elif mode == 'margin_b':
            return self.margin_b,    
        else: # mode == 'max':
            return self.max
        
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
        '''        
        # Readability:
        cr = self.cr
        uid = self.uid
        context = {}
        product_pool = self.pool.get('product.product')
        
        # Default reference for take price is 500 days before:
        days = 500 # valid price
        date_ref = (datetime.now() - timedelta(days=500)).strftime(
            DEFAULT_SERVER_DATE_FORMAT)
        
        res = []
        selected_product = product_pool._report_industrial_get_objects(
            cr, uid, data=data, context=context)
        if selected_product:    
            margin_a = \
                selected_product[0].company_id.industrial_margin_a / 100.0 
            margin_b = \
                selected_product[0].company_id.industrial_margin_b / 100.0 
                
        for product in selected_product:
                
            data = [
                0.0, # 0. Min
                0.0, # 1. Max
                False, # 2. Error
                [], # 3. Component data
                [], # 4. Extra cost (1) industrial
                [], # 5. Extra cost (2) work
                {}, # 6. Index (total for calculate index)
                {}, # 7. Total (margin element)
                product, # 8. Product browse
                ]

            # -----------------------------------------------------------------
            # Load component list (and subcomponent for HW):
            # -----------------------------------------------------------------
            for item in product.dynamic_bom_line_ids:
                component = item.product_id
                half_bom_ids = component.half_bom_ids # if half component
                if half_bom_ids: 
                    # HW component (level 2)                    
                    for cmpt in half_bom_ids:
                        #last_date = False # TODO last price?
                        cmpt_q = item.product_qty * cmpt.product_qty # XXX                        
                        min_value, max_value, price_ids = get_pricelist(
                            product, cmpt_q, date_ref)
                                     
                        # TODO manage as pipe?
                        record = [
                            '%s - %s >> %s' % (
                                cmpt.product_id.default_code or '',
                                cmpt.product_id.name or '',
                                component.default_code or '', # HW 
                                ),
                            cmpt_q, # q. total
                            cmpt.product_id.uom_id.name, # UOM
                            max_value, # unit price (max not the last!)
                            max_value * cmpt_q, # subtotal (last = unit x q)
                            price_ids, # list of all prices (XXX not used)
                            ]

                        if not max_value: 
                            error = True # This product now is in error!
                                     
                        # Update min and max value:             
                        data[0] += min_value
                        data[1] += max_value
                        data[3].append(record) # Populate product database
                else: 
                    # Raw material (level 1)
                    min_value, max_value, price_ids = get_pricelist(
                        product, cmpt_q, date_ref)
                    data[3].append([
                        '%s - %s' % (
                            component.default_code or '',
                            component.name or '',
                            ),
                        item.product_qty, # q. total
                        component.uom_id.name, # UOM
                        max_value, # unit price (max not the last!)
                        item.product_qty * max_value, # subtotal
                        price_ids, # list of all prices
                        ]) # Populate product database

            # Sort collected data:
            data[3].sort() # First element is name
            
            # -----------------------------------------------------------------
            # Extra data end report:
            # -----------------------------------------------------------------
            data[5] = { # Index
                _('Componenti'): self.max, # used max:
                }            
            for cost, item in product_pool.get_cost_industrial_for_product(
                    cr, uid, [product.id], context=context).iteritems():
                # Index total:    
                if cost.type not in data[6]: 
                    data[6][cost.type] = 0.0
                    
                # 2 case: with product or use unit_cost    
                if item.product_id: # use item price
                    value = item.qty * item.last_cost                
                    time_qty = False
                else:
                    value = item.qty * cost.unit_cost                     
                    time_qty = item.qty
                
                if cost.type == 'industrial':
                    data[4].append((item or '???', value, time_qty))
                else: #'work'    
                    data[5].append((item or '???', value, time_qty))
                
                data[0] += value # min
                data[1] += value # max
                data[6][cost.type] += value # Index total

            # Save margin parameters:        
            data[7]['margin_a'] = data[1] * industrial_margin_a / 100.0 
            data[7]['margin_b'] = data[1] * industrial_margin_b / 100.0 
                
            # Write status in row:    
            data[7]['index'] = industrial_index_get_text(data[6])
            if context.get('update_record', True): # XXX always true for now:
                product_pool.write(cr, uid, product.id, {
                    'from_industrial': data[0],
                    'to_industrial': data[1],
                    'industrial_missed': data[2],
                    'industrial_index': data[7]['index'],
                    }, context=context)            
            res.append(data)
        return res

    def get_details(self, product):
        ''' Create detail row
        '''
        cr = self.cr
        uid = self.uid
        context = {}

        # Pool used:    
        product_pool = self.pool.get('product.product')
        return product_pool._report_industrial_get_details(
            cr, uid, product, context=context)
        
    def get_totals(self, mode):
        ''' Total value (min or max)
        '''    
        product_pool = self.pool.get('product.product')
        return product_pool._report_industrial_get_totals(mode)
