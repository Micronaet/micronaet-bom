# -*- coding: utf-8 -*-
###############################################################################
#
#    Copyright (C) 2001-2014 Micronaet SRL (<http://www.micronaet.it>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import os
import sys
import logging
import openerp
import xlrd
import xlsxwriter
import openerp.netsvc as netsvc
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID, api
from openerp import tools
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)

class ResCompany(orm.Model):
    """ Model name: ResCompany
    """
    _inherit = 'res.company'
    
    # Procedure:    
    def import_barcode(self, cr, uid, ids, context=None):
        ''' Import barcode
        '''
        ''' Read XLS file for reassociate inventory category
        ''' 
        def generate_code_from_cell(value):
            ''' Add extra char
            '''
            import barcode
            EAN = barcode.get_barcode_class('ean13')
            if len(value) != 12:
                raise osv.except_osv(
                    _('Error'),
                    _('EAN before control must be 12 char!'))
            ean13 = EAN(value)
            return ean13.get_fullcode()
        
        filename = '/home/administrator/photo/xls/ean/barcode.xls'
        product_pool = self.pool.get('product.product')

        try:
            WB = xlrd.open_workbook(filename)
        except:
            raise osv.except_osv(
                _('Error XLSX'), 
                _('Cannot read XLS file: %s' % filename),
                )
                
        WS = WB.sheet_by_index(0)
        for row in range(0, WS.nrows):
            default_code = WS.cell(row, 0).value
            
            data = {} 
            try:       
                ean13_s = generate_code_from_cell(
                    '%s' % int(WS.cell(row, 2).value))
            except:
                ean13_s = ''
                _logger.error(
                    'Cannor convert EAN: %s' % (WS.cell(row, 2).value))
            if ean13_s and len(ean13_s) == 13: 
                data['ean13_mono'] = ean13_s

            try:
                ean13 = generate_code_from_cell(
                    '%s' % int(WS.cell(row, 3).value)) # pack
            except:
                ean13 = ''
                _logger.error(
                    'Cannor convert EAN: %s' % (WS.cell(row, 3).value))
            if ean13 and len(ean13) == 13:
                data['ean13'] = ean13
            
            if not data:
                _logger.info('No data in this row %s' % default_code)
                continue
                
            # Write ean 13 of product and single:            
            product_ids = product_pool.search(cr, uid, [
                ('default_code', '=', default_code),
                ], context=context)
            if product_ids:
                product_pool.write(cr, uid, product_ids, data, context=context)
                _logger.info('Update: %s %s' % (default_code, data))

            # Write ean 13 for single if exist:
            if len(default_code) > 12 or not ean13_s:
                _logger.info('Single unmanaged: %s' % default_code)
                continue # unmanaged single
            
            default_code_s = '%-12sS' % default_code
            _logger.info('Search Single: %s' % default_code_s)
            product_ids = product_pool.search(cr, uid, [
                ('default_code', '=', default_code_s),
                ], context=context)
            if product_ids:
                product_pool.write(cr, uid, product_ids, {
                    'ean13': ean13_s,
                    #'ean13_mono': ean13_s, # not written
                    }, context=context)
                _logger.info('Update S: %s %s' % (default_code_s, ean13_s))
        
        return True
        
    def get_excel_evaluation_supplier(self, cr, uid, ids, context=None):
        ''' Import code, export extra data for purchase
        '''
        filename = '/home/administrator/photo/xls/inventory/product.csv'
        data = '/home/administrator/photo/xls/inventory/product_with_data.csv'
        
        product_pool = self.pool.get('product.product')
        codes = []   
        try:     
            f_in = open(filename, 'r')
        except:
            raise osv.except_osv(
                _('Error open file'), 
                _('Not found: %s' % filename),
                ) 
                         
        for item in f_in:
            code = item.strip()
            codes.append(code)
        
        product_ids = product_pool.search(cr, uid, [
            ('default_code', 'in', codes),
            ], context=context)    
        
        f_out = open(data, 'w')
        for product in product_pool.browse(
                cr, uid, product_ids, context=context):
                
            cost = 0.0
            supplier = ''
            old_date = False
            not_found = True
            for seller in product.seller_ids:
                for pl in seller.pricelist_ids:
                    current_date = pl.write_date
                    if not old_date or old_date < current_date:
                        old_date = current_date
                        not_found = False
                        cost = pl.price
                        supplier = seller.name.name
            cost = ('%s' % cost).replace('.', ',')
            row = '%s|%s|%s|%s|%s\n' % (
                product.default_code,
                cost,
                supplier,
                old_date,
                '?' if not_found else '',
                )
            f_out.write(row)
        return True
        
        
    def correct_inventory_category(self, cr, uid, ids, context=None):
        ''' Read XLS file for reassociate inventory category
        ''' 
        filename = '/home/administrator/photo/xls/inventory/category.xls'
        #product.product.inventory.category
        try:
            WB = xlrd.open_workbook(filename)
        except:
            raise osv.except_osv(
                _('Error XLSX'), 
                _('Cannot read XLS file: %s' % filename),
                )
        WS = xl_workbook.sheet_by_index(0)
        for row in range(0, WS.nrows):
            default_code = WS.cell(row, 0)
            category_name = WS.cell(row, 1)
            print default_code, category_name
        return True

    def export_ordered_product_for_label_check_product(
            self, cr, uid, ids, context=None):    
        ''' Export product ordered for check label fields
        '''    
        # ---------------------------------------------------------------------
        # Create and open Workbook:
        # ---------------------------------------------------------------------        
        # Pool used:        
        product_pool = self.pool.get('product.product')
        sol_pool = self.pool.get('sale.order.line')

        sol_ids = sol_pool.search(cr, uid, [
            ('order_id.state', 'not in', ('draft', 'sent', 'cancel')),
            ('order_id.mx_closed', '=', False),
            ], context=context)
        _logger.info('Selected order line: %s' % len(sol_ids))
        
        product_ids = [item.product_id.id for item in sol_pool.browse(
            cr, uid, sol_ids, context=context)]
        product_ids = list(set(product_ids))
        _logger.info('Selected product: %s' % len(product_ids))
        
        product_ids = product_pool.search(cr, uid, [
            ('id', 'in', product_ids),
            ('ean13', '=', False),
            ], context=context)
        
        _logger.info('Selected product no barcode: %s' % len(product_ids))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Product in OC'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            #'res_id': 1,
            'res_model': 'product.product',
            #'view_id': view_id, # False
            'views': [(False, 'tree'), (False, 'form')],
            'domain': [('id', 'in', product_ids)],
            'context': context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }        
        
    def export_ordered_product_for_label_check(
            self, cr, uid, ids, context=None):    
        ''' Export product ordered for check label fields
        '''    
        # ---------------------------------------------------------------------
        # Create and open Workbook:
        # ---------------------------------------------------------------------
        xls_file = '/home/administrator/photo/xls/label/ordered_product.xlsx'
        _logger.info('Start export label check: %s' % xls_file)    
        
        WB = xlsxwriter.Workbook(xls_file)
        WS = WB.add_worksheet('Prodotti ordinati')
        
        # Pool used:        
        product_pool = self.pool.get('product.product')
        sol_pool = self.pool.get('sale.order.line')

        sol_ids = sol_pool.search(cr, uid, [
            ('order_id.state', 'not in', ('draft', 'sent', 'cancel')),
            ('order_id.mx_closed', '=', False),            
            ], context=context)
        _logger.info('Row selected: %s' % len(sol_ids))    
        
        product_ids = [item.product_id.id for item in sol_pool.browse(
            cr, uid, sol_ids, context=context)]
        product_ids = list(set(product_ids))
        product_proxy = product_pool.browse(
            cr, uid, product_ids, context=context)
        
        # Write header:                
        row = 0
        WS.write(row, 0, 'Codice')
        WS.write(row, 1, 'EAN 13')
        WS.write(row, 2, 'Ean 13 mono')
        WS.write(row, 3, 'EAN 8')
        WS.write(row, 4, 'Ean 8 mono')
        WS.write(row, 5, 'Q x pack')
        WS.write(row, 6, 'Q x pallet')
        
        for product in sorted(product_proxy, key=lambda x: x.default_code):
            # Write data line:            
            row += 1            
            WS.write(row, 0, product.default_code)
            WS.write(row, 1, product.ean13)
            WS.write(row, 2, product.ean13_mono)
            WS.write(row, 3, product.ean8)
            WS.write(row, 4, product.ean8_mono)
            WS.write(row, 5, product.q_x_pack)
            WS.write(row, 6, product.q_x_pallet or product.item_per_pallet)
        WB.close()
        _logger.info('Start export label check: %s' % xls_file)    
        return True
        
    def pipe_status_export(self, cr, uid, ids, context=None):
        ''' Extract pipe status for inventory check
        '''
        stock_id = 12 # XXX
        
        # ---------------------------------------------------------------------
        # Create and open Workbook:
        # ---------------------------------------------------------------------
        xls_file = '/home/administrator/photo/output/pipe_stock.xlsx'
        
        WB = xlsxwriter.Workbook(xls_file)
        WS = WB.add_worksheet('Inventario tubi')
        
        product_pool = self.pool.get('product.product')
        move_pool = self.pool.get('stock.move')
        
        pipe_ids = product_pool.search(cr, uid, [
            ('is_pipe', '=', True)], context=context)
        
        move_ids = move_pool.search(cr, uid, [
            ('product_id', 'in', pipe_ids)
            ], order='product_id, date', context=context)
        move_proxy = move_pool.browse(cr, uid, move_ids, context=context)
        
        status = {} # progress status
        inventory = {} # for check start with old movement
        res = []
        old_product = False
        row = 0
        WS.write(row, 0, 'Codice')
        WS.write(row, 1, 'Inventario')
        WS.write(row, 2, 'Data')
        WS.write(row, 3, 'Documento')
        WS.write(row, 4, 'Movimento')
        WS.write(row, 5, 'Quantita')
        WS.write(row, 6, 'Saldo')
        WS.write(row, 7, 'Negativo')
        WS.write(row, 8, 'Inventario')
        
        for move in move_proxy:
            row += 1
            product = move.product_id
            date = move.date
            
            # Save inventory:
            if product not in inventory:
                inventory[product] = product.mx_start_qty

            # Control sign of operation
            if move.location_dest_id.id == stock_id: # IN
                move_sign = +1
            else:
                move_sign = -1
                
            # Relative total:    
            qty = move_sign * move.product_qty
            
            if product not in status:
                row += 1 # jump line
                status[product] = 0.0
                            
            if date >= '2017' and status[product] != inventory[product]:
                error = 'X'
            else:
                error = ''
                
            if move.state == 'done':
                status[product] += qty
                of = False
            else:
                of = True
            
            if move.picking_id:
                picking = move.picking_id.name
            else:
                picking = ''  

            # TODO check negative status            
            WS.write(row, 0, product.default_code)
            WS.write(row, 1, product.mx_start_qty)
            WS.write(row, 2, move.date)
            WS.write(row, 3, '%s %s' % (move.origin or '', picking))
            WS.write(row, 4, 'OF' if of else (
                'IN' if move_sign > 0 else 'OUT'))
            WS.write(row, 5, qty)
            WS.write(row, 6, '' if of else status[product])
            WS.write(row, 7, 'X' if status[product] < 0 else '')
            WS.write(row, 8, error)
            
            
        return True
            
    def create_dynamic_rule(self, cr, uid, ids, context=None):
        ''' Create rule for MT MS
        '''
        category_pool = self.pool.get('mrp.bom.structure.category')
        product_pool = self.pool.get('product.product')
        bom_pool = self.pool.get('mrp.bom')
        line_pool = self.pool.get('mrp.bom.line')
        
        # Search dynamic BOM:
        bom_ids = bom_pool.search(cr, uid, [
            ('bom_category', '=', 'dynamic')
            ], context=context)
        if not bom_ids:
            raise osv.except_osv(
                _('BOM Error'), 
                _('No dynamic bom'),
                )    
        dynamic_id = bom_ids[0]        

        loop = [
            # Category, log, 
            (
                'Materassino', 
                '/home/administrator/photo/log/materassini_MT_MS.log', 
                'MT', 
                'MS',
                 ),
            (
                'Telo', 
                '/home/administrator/photo/log/teli_TL_TS.log', 
                'TL', 
                'TS'),
            ]
             
        for category, log_file, from_code, to_code, in loop:
            _logger.warning('Start block: %s [log: %s]' % (category, log_file))
            
            # Search category:
            category_ids = category_pool.search(cr, uid, [
                ('name', '=', category)
                ], context=context)
            if not category_ids:
                raise osv.except_osv(
                    _('BOM Error'), 
                    _('No category %s' % category),
                    )    
            category_id = category_ids[0]        
                    
            # Search all MT product    
            product_ids = product_pool.search(cr, uid, [
                ('default_code', '=ilike', '%s%%' % from_code),
                ], context=context)        
            comment = _('Product|Component|Mask|Note\n')

            for product in product_pool.browse(
                    cr, uid, product_ids, context=context):   
                # Generate code:    
                default_code = product.default_code
                dynamic_mask = '%s%%' % default_code[:12] # no 13 char (S)
                hw_code = '%s%s' % (to_code, default_code[2:])
                
                # Search HW code
                product_ids = product_pool.search(cr, uid, [
                    ('default_code', '=', hw_code)], context=context)
                
                if not product_ids: # Product HW not found!
                    comment += '%s|%s|%s|%s\n' % (
                        default_code,
                        hw_code,
                        dynamic_mask,
                        _('No HW component found!'),
                        )
                    continue
                product_id = product_ids[0]    
                # more than one raise?    
                    
                # Search dynamic rule for product-component:
                line_ids = line_pool.search(cr, uid, [
                    ('bom_id', '=', dynamic_id),
                    ('dynamic_mask', '=', dynamic_mask),
                    ('product_id', '=', product_id),
                    ], context=context)
                if line_ids: 
                    # rule present
                    comment += '%s|%s|%s|%s\n' % (
                        default_code,
                        hw_code,
                        dynamic_mask,
                        _('Yet present!'),
                        )
                else:
                    # Create rule
                    line_pool.create(cr, uid, {
                        'bom_id': dynamic_id,
                        'product_id': product_id,
                        'dynamic_mask': dynamic_mask,
                        'product_uom': 1, # XXX
                        'product_qty': 1.0,     
                        'category_id': category_id,               
                        }, context=context)
                    
                    comment += '%s|%s|%s|%s\n' % (
                        default_code,
                        hw_code,
                        dynamic_mask,
                        _('New rule'),
                        )
                        
            # Write log:            
            f_log = open(log_file, 'w')        
            f_log.write(comment)
            f_log.close()
        return True
        
    def check_bom_half_error_linked(self, cr, uid, ids, context=None):
        ''' Check error during operation on bom
        '''
        # Pool used:
        product_pool = self.pool.get('product.product')

        # Reset selection:
        temp_ids = product_pool.search(cr, uid, [
            ('temp_selection', '=', True)], context=context)
        if temp_ids:  
            product_pool.write(cr, uid, temp_ids, {
                'temp_selection': False}, context=context)
            _logger.warning('Uncheck %s product record' % len(temp_ids))
            
        # Check HW bon link:
        product_ids = product_pool.search(cr, uid, [
            ('relative_type', '=', 'half')], context=context)
        temp_ids = []
        for product in product_pool.browse(
                cr, uid, product_ids, context=context):        
            # XXX Now also empty elements?        
            if product.half_bom_id.halfwork_id.id != product.id:
                temp_ids.append(product.id)
        
        # Update temp selection
        _logger.warning('Check %s product record' % len(temp_ids))
        return product_pool.write(cr, uid, temp_ids, {
            'temp_selection': True}, context=context)
        
    def generate_pipe_from_hw(self, cr, uid, ids, context=None):
        ''' Import hw component, output pipe
        '''
        in_file = '/home/administrator/photo/import_tubi.csv'
        out_file = '/home/administrator/photo/output_tubi.csv'
        separator = '|'
        
        f_in = open(in_file, 'r')
        f_out = open(out_file, 'w')
        
        # Pool used:
        product_pool = self.pool.get('product.product')
        
        i = 0
        _logger.info('Start read: %s' % in_file)
        _logger.info('Start out: %s' % out_file)
        for line in f_in:
            i += 1
            line = line.strip().split(separator)
            if len(line) != 3:
                _logger.error('Column error')
                continue
                
            # Read columns:    
            bom = line[0]
            hw = line[1]  
            quantity = line[2]
            
            product_ids = product_pool.search(cr, uid, [
                ('default_code', '=', hw),
                ('relative_type', '=', 'half'),
                ], context=context)
            if not product_ids:
                _logger.error('No HW code: %s' % hw)
                continue    

            if len(product_ids) > 1:
                _logger.warning('More HW code: %s' % hw)
                #continue
            
            product_proxy = product_pool.browse(
                cr, uid, product_ids, context=context)[0]
            f_out.write('%s|%s\n' % (
                product_proxy.half_bom_ids[0].product_id.default_code,
                quantity,
                ))

        _logger.info('End read: %s > %s' % (in_file, out_file))

class ProductProduct(orm.Model):
    """ Model name: ProductProduct
    """
    
    _inherit = 'product.product'
    
    _columns = {
        'temp_selection': fields.boolean('Temp selection'),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
