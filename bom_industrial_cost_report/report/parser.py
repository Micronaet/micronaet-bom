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
        if key not in type_i18n: 
            continue # jump key not used
        res += '%s: %6.3f su %6.3f = %s%%\r\n' % (
            type_i18n[key], 
            value, index_total,
            ('%6.3f' % (100.0 * value / index_total, )) if \
                index_total else 'ERRORE!',
            )
    return res
    
def get_pricelist(product, date_ref):
    ''' Return:
        min price, max price, all pricelist for this product
        active price, reference >= passed
    '''
    res = [
        0.0, # Min (not False)
        0.0, # Max
        [], # Price list
        ]
        
    last_price = [False, False] # Price, Date
    for seller in product.seller_ids:
        for pricelist in seller.pricelist_ids:
            # no inactive price XXX remove this filter?
            if not pricelist.is_active: # no inactive
                continue   
             
            # Take only period date:
            price = pricelist.price
            date_quotation = pricelist.date_quotation
            
            if not last_price[1] or (
                    date_quotation and date_quotation > last_price[1]):
                last_price[0] = price
                last_price[1] = date_quotation or False
                                              
            res[2].append((
                seller.name, # Supplier browse
                price, # Unit price
                date_quotation, # Date
                ))

            # Keep here for analyse only one price:             
            if pricelist.date_quotation and \
                   pricelist.date_quotation <= date_ref:
                continue

            # Save min or max price:    
            if not res[0] or price < res[0]: # 0 price will be replaced
                res[0] = price
            if price > res[1]:
                res[1] = price

    if not res[0] and last_price[0]: # if not price but there's last
        # Keep the same:
        res[0] = last_price[0]
        res[1] = last_price[0]
    return res             

def is_fabric_product(product):
    ''' Is fabric test
        return dimension        
    '''
    # Start with T
    default_code = product.default_code
    if not default_code or len(default_code) < 6:
        return False
        
    if not default_code.startswith('T'):
        return False
        
    # UOM is meter:    
    if product.uom_id.name != 'm': 
        return False
    
    # Has TEX001 format:
    for (from_c, to_c) in [(3, 6), (6, 9)]:
        h = product.default_code[from_c:to_c]
        is_fabric = True
        for c in h:
            if not c.isdigit():
                is_fabric = False
                
        if is_fabric:
            try:
                return float(h) / 100.0 # meter
            except:
                _logger.error('Error convert %s to float' % h)
                return 0.0    
    return False         

def get_price_detail(price_ids):
    ''' With detail
    '''
    res = ''
    # If not detail:
    return res # XXX no detail mode
    for seller, price, date_quotation in price_ids:
        res += '%s EUR (%s) %s \n' % (
            price, # Unit price
            date_quotation,
            seller.name, # Supplier browse
            )
    return res        

def get_price_2016(price_ids, current):
    ''' With detail
    '''
    res = ''
    last_date = False
    last_price = 0
    
    # If not detail:
    for seller, price, date_quotation in price_ids:
        if not last_date and date_quotation <= '2017-01-01' and \
                date_quotation > last_date and price != current:
            res = 'Forn.: %s %s EUR (%s) \n' % (
                seller.name, # Supplier browse
                price, # Unit price
                date_quotation,
                )
    return res        

class ProductProduct(orm.Model):
    """ Model name: ProductProduct add utility for report
    """
    
    _inherit = 'product.product'
    
    # -------------------------------------------------------------------------
    # Button event:
    # -------------------------------------------------------------------------
    def get_medea_data(self, value):
        return ''

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
        ''' Return xls report extracted from get_object method
        '''
        # ---------------------------------------------------------------------
        # Utility:
        # ---------------------------------------------------------------------
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
  
        # ---------------------------------------------------------------------
        # Setup excel layout and columns:
        # ---------------------------------------------------------------------
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
        # Extract data from ODT master function:
        row = 0
        for (r_min, r_max, r_error, r_components, r_extra1, r_extra2, r_index, 
            r_total, product, r_parameter, r_total_text, pipe_data) in \
                self.report_get_objects_bom_industrial_cost(
                    cr, uid, datas=datas, context=context):
            row += 1       
                 
            # Detault data:
            row_data = [
                product.default_code, 
                product.name, 
                r_min, 
                r_max,
                'X' if r_error else '',
                ]
            
            # Extra column for costs:
            industrial_cost = [0.0 for col in range(0, len(cost_db))]            
            
            # Loop on 2 cost table (industrial cost):
            for table in (r_extra1, r_extra2): 
                for item, details, time_qty in table:
                    if time_qty:                    
                        industrial_cost[cost_db[item.cost_id.name]] = \
                            '%s (T. %s)' % (details, time_qty)
                    else:        
                        industrial_cost[cost_db[item.cost_id.name]] = details

            # -----------------------------------------------------------------
            # Print XLS row data:
            # -----------------------------------------------------------------
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
           
        return sorted(objects, key=lambda o: o.default_code)

    def report_get_objects_bom_industrial_cost(self, cr, uid, datas=None, 
            context=None):
        ''' Report action for generate database used (both ODT and XLSX export)
        '''
        if datas is None:
            datas = {}
        update_record = datas.get('update_record', False)
        if update_record:
            _logger.warning('Product price will be updated from report!')
        else:    
            _logger.warning('No product price updated!')

        res = []
        selected_product = self._report_industrial_get_objects(
            cr, uid, data=datas, context=context)
        if selected_product:    
            margin_a = \
                selected_product[0].company_id.industrial_margin_a
            margin_b = \
                selected_product[0].company_id.industrial_margin_b
            # TODO manage extra:    
            margin_extra = \
                selected_product[0].company_id.industrial_margin_extra

            days = selected_product[0].company_id.industrial_days or 500
            date_ref = (datetime.now() - timedelta(days=days)).strftime(
                DEFAULT_SERVER_DATE_FORMAT)
        
            parameter = _('Parametri: Margine A: %s%% - Margine B: %s%% - '
                'Margine extra: %s%% Giorni date rif. prezzi -%s') % (
                    margin_a,
                    margin_b,
                    margin_extra,
                    days,
                    )
        else:        
            return res
                
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
                '', # 9. Parameter of report
                '', # 10. Total text
                [0.0, 0.0], # 11. Pipe weight total (q, total)
                ]

            # -----------------------------------------------------------------
            # Load component list (and subcomponent for HW):
            # -----------------------------------------------------------------
            for item in product.dynamic_bom_line_ids:                
                component = item.product_id
                if component.bom_placeholder or component.bom_alternative:
                    _logger.warning('Jump placeholder elements')
                    continue # jump component
                    
                half_bom_ids = component.half_bom_ids # if half component
                if half_bom_ids: 
                    # HW component (level 2)                    
                    for cmpt in half_bom_ids:
                        #last_date = False # TODO last price?
                        cmpt_q = item.product_qty * cmpt.product_qty # XXX                        
                        min_value, max_value, price_ids = get_pricelist(
                            cmpt.product_id, date_ref)                        
                        price_detail = get_price_detail(price_ids)

                        # Fabric element:
                        is_fabric = is_fabric_product(cmpt.product_id)
                        uom_name = cmpt.product_id.uom_id.name
                        fabric_text = ''
                        if is_fabric:
                            fabric_text = '(MQ: %8.5f EUR/MQ: %8.5f)' % (
                                cmpt_q * is_fabric,
                                max_value / is_fabric,
                                )
                            
                        # Pipe element:    
                        if cmpt.product_id.is_pipe:
                            # Calc with weight and price kg not cost manag.:
                            pipe_price = \
                                cmpt.product_id.pipe_material_id.last_price
                            min_value = max_value = \
                                pipe_price * cmpt.product_id.weight

                            # Total pipe weight:    
                            q_pipe = item.product_qty * cmpt.product_qty *\
                                cmpt.product_id.weight
                            data[11][0] += q_pipe
                            data[11][1] += q_pipe * pipe_price
                                     
                        # TODO manage as pipe?
                        red_price = \
                            not cmpt.product_id.bom_industrial_no_price and \
                                not max_value
                        if cmpt.product_id.bom_industrial_no_price:
                            min_value = max_value = 0.0 # no price in BOM
                            
                        record = [
                            '%s - %s' % (
                                cmpt.product_id.default_code or '',
                                cmpt.product_id.name or '',
                                ),
                            cmpt_q, # q. total
                            uom_name, # UOM
                            max_value, # unit price (max not the last!)
                            max_value * cmpt_q, # subtotal (last = unit x q)
                            price_detail, # list of price (used for detail)
                            component, # HW product
                            cmpt.product_id, # Product for extra data
                            red_price, # no price
                            fabric_text, # fabric text for price
                            # TODO 2016 evaluation if different!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                            get_price_2016(price_ids, max_value),
                            ]

                        if red_price:
                            data[2] = True # This product now is in error!
                                     
                        # Update min and max value:             
                        data[0] += min_value * cmpt_q
                        data[1] += max_value * cmpt_q
                        
                        data[3].append(record) # Populate product database
                else: 
                    # Raw material (level 1)                    
                    cmpt_q = item.product_qty
                    min_value, max_value, price_ids = get_pricelist(
                        item.product_id, date_ref)
                    price_detail = get_price_detail(price_ids)

                    red_price = \
                        not component.bom_industrial_no_price and not max_value
                    if component.bom_industrial_no_price:
                        min_value = max_value = 0.0
                    data[3].append([
                        '%s - %s' % (
                            component.default_code or '',
                            component.name or '',
                            ),
                        cmpt_q, # q. total
                        component.uom_id.name, # UOM
                        max_value, # unit price (max not the last!)
                        max_value * item.product_qty, # subtotal
                        price_detail, # list of price (used for detail), 
                        False, # HW product (not here)
                        component, # Product for extra data
                        red_price, # Prod with no price
                        '', # fabric text for price
                        get_price_2016(price_ids, max_value), # TODO !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                        ]) # Populate product database
                        
                    if red_price:
                        data[2] = True # This product now is in error!
                        
                    data[0] += min_value * cmpt_q
                    data[1] += max_value * cmpt_q

            # Add extra (save in total the max)
            data[0] += data[0] * margin_extra / 100.0
            margin_extra_value = data[1] * margin_extra / 100.0
            
            # Update total text:
            data[10] += '%10.5f +%10.5f'  % (
                data[1],
                margin_extra_value,
                )
            
            data[1] += margin_extra_value
            
            # -----------------------------------------------------------------
            # Extra data end report:
            # -----------------------------------------------------------------
            data[6] = { # Index
                _('component'): data[1], # used max:
                }            
            for cost, item in self.get_cost_industrial_for_product(
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

                if item.cost_id.name == 'Manodopera MEDEA':
                    value = self.get_medea_data(item.name)
                cost_item = (item or '???', value, time_qty)
                if cost.type == 'industrial':
                    data[5].append(cost_item)
                elif cost.type == 'work':
                    data[4].append(cost_item)
                else:
                    raise osv.except_osv(
                        _('Tipo errato'), 
                        _('Tipo di costo non presente'),
                        )
                
                data[0] += value # min
                data[1] += value # max
                data[6][cost.type] += value # Index total

            # Save margin parameters:
            data[7]['margin_a'] = data[1] * margin_a / 100.0
            data[7]['margin_b'] = data[1] * margin_b / 100.0
            
                
            # Write status in row:    
            data[7]['index'] = industrial_index_get_text(data[6])
            if update_record:
                self.write(cr, uid, product.id, {
                    'from_industrial': data[0],
                    'to_industrial': data[1],
                    'industrial_missed': data[2],
                    'industrial_index': data[7]['index'],
                    }, context=context)  
                       
            # Total text:      
            # Mat + Extra + Cost1 + Cost2
            for t in type_i18n:
                if t in data[6]:
                    data[10] += ' +%8.5f' % data[6][t]

            # Sort data:
            data[3].sort(key=lambda x: x[0]) # XXX raise error without key
            data[4].sort(key=lambda x: x[0].cost_id.name) # Table 1
            data[5].sort(key=lambda x: x[0].cost_id.name) # Table 2
            res.append(data)
        
        # Update parameters:    
        res[0][9] = parameter
        return res

class Parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(Parser, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'get_objects': self.get_objects,
            #'get_details': self.get_details,
            #'get_totals': self.get_totals,
        })
        
    def get_objects(self, datas=None):
        ''' Return single report or list of selected bom 
        '''        
        # Readability:
        cr = self.cr
        uid = self.uid
        context = {}
        product_pool = self.pool.get('product.product')
        
        return product_pool.report_get_objects_bom_industrial_cost(
            cr, uid, datas=datas, context=context)

