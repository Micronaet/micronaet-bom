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

_logger = logging.getLogger(__name__)


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
        cost_ids = cost_pool.search(cr, uid, [], context=context)
        i = 0
        for cost in cost_pool.browse(cr, uid, cost_ids, context=context):
            cost_db[cost.name] = i # position in Excel file
            i += 1
        
        header = [
            _('Code'), 
            _('Description'), 
            _('Min'), 
            _('Max'), 
            _('Price not present')]
        header.extend(cost_db.keys())
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
            for mode, item, details in self._report_industrial_get_details(
                    cr, uid, product, context=context):
                if mode in ('C', 'S'):
                    if not details: # Check if not details 
                        not_details = True
                elif mode == 'T':
                    # Industrial cost
                    industrial_cost[cost_db[item]] = details                    
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
        '''        # Readability:
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
        objects = self.browse(
            cr, uid, active_ids, context=context)
           
        return objects #sorted(objects, key=lambda o: o.default_code)

    def _report_industrial_get_details(self, cr, uid, product, context=None):
        ''' Create detail row
        '''
        # ---------------------------------------------------------------------
        # Utility:
        # ---------------------------------------------------------------------
        def load_subelements_price(self, res, mode, item, product, hw=False):
            ''' Load list in all seller pricelist return min and max value
            '''
            min_value = 0.0
            max_value = 0.0
            
            record = [mode, item, []]
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
            return

        # ---------------------------------------------------------------------
        # Load component list (and subcomponent for HW):
        # ---------------------------------------------------------------------
        res = []
        # Min / Max totals:
        self.min = 0.0
        self.max = 0.0
        for item in product.dynamic_bom_line_ids:
            component = item.product_id
            half_bom_ids = component.half_bom_ids # if half component
            if half_bom_ids: # HW component
                for cmpt in half_bom_ids:
                    load_subelements_price(
                        self, res, 'S', cmpt, cmpt.product_id, 
                        item.product_id.default_code,
                        )
            else: # not HW component
                load_subelements_price(
                    self, res, 'C', item, item.product_id)

        # ---------------------------------------------------------------------
        # Extra data end report:
        # ---------------------------------------------------------------------
        # Add header:
        res.append(('H', False, False))    

        # Add lavoration cost:
        cost_industrial = self.get_cost_industrial_for_product(
            cr, uid, [product.id], context=context)
        for cost, value in cost_industrial.iteritems():
            res.append(('T', cost, value))    
            self.min += value
            self.max += value
        return res

    def _report_industrial_get_totals(self, mode):
        ''' Total value (min or max)
        '''    
        if mode == 'min':
            return self.min
        else:
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
        '''        # Readability:
        cr = self.cr
        uid = self.uid
        context = {}
        product_pool = self.pool.get('product.product')
        
        return product_pool._report_industrial_get_objects(
            cr, uid, data=data, context=context)

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
