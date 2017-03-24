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
import xlsxwriter
import xlrd
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
from inventory_present import product_present

_logger = logging.getLogger(__name__)

class ResCompany(orm.Model):
    """ Model name: ResCompany
    """
    _inherit = 'res.company'

    def check_invoice_line(self, cr, uid, ids, context=None):
        ''' Check invoice line
        '''
        filename = '/home/administrator/photo/xls/check_invoice.xls'                
        
        invoice_pool = self.pool.get('account.invoice')
        invoice_ids = invoice_pool.search(cr, uid, [
            ('date_invoice', '>=', '2017-01-01')], context=context)

        # Open file and write header
        WB = xlsxwriter.Workbook(filename)
        WS = WB.add_worksheet('Fatture')
        WS.write(0, 0, 'Fattura')
        WS.write(0, 1, '# righe')
        WS.write(0, 2, '# stock')

        i = 0
        for invoice in invoice_pool.browse(
                cr, uid, invoice_ids, context=context):
            invoice_line = len(invoice.invoice_line)
            stock_line = 0
            for stock in invoice.invoiced_picking_ids:
                stock_line += len(stock.move_lines)
            if invoice_line != stock_line:                
                _logger.warning(invoice.number)
                i += 1
                WS.write(i, 0, invoice.number)
                WS.write(i, 1, invoice_line)
                WS.write(i, 2, stock_line)
        WB.close()
        return True
        
    def import_pricelist_with_parent(self, cr, uid, ids, context=None):
        ''' Import pricelist with parent code 
            >> ordered for overlap problem
        '''
        product_pool = self.pool.get('product.product')

        filename = '/home/administrator/photo/xls/pricelist.xls'
        log = '/home/administrator/photo/xls/pricelist_log.csv'

        try:
            WB = xlrd.open_workbook(filename)
        except:
            raise osv.except_osv(
                _('Error XLSX'), 
                _('Cannot read XLS file: %s' % filename),
                )

        total_ids = [] # Write log

        # ---------------------------------------------------------------------        
        # Load current list:                
        # ---------------------------------------------------------------------    
        WS = WB.sheet_by_index(0)
        for row in range(1, WS.nrows):
            parent = WS.cell(row, 0).value            
            price = WS.cell(row, 1).value
            
            if type(parent) == float:
                parent = '%s' % int(parent)
            
            product_ids = product_pool.search(cr, uid, [
                ('default_code', '=ilike', '%s%%' % parent)], context=context)
            if not product_ids:
                continue
                    
            _logger.info('Update %s with %s [tot: %s]' % (
                parent, price, len(product_ids)))            
            total_ids.extend(product_ids) # Append for log
            product_pool.write(cr, uid, product_ids, {
                'lst_price': price,
                }, context=context)
        
        total_ids = tuple(set(total_ids))

        log_f = open(log, 'w')
        for product in product_pool.browse(
                cr, uid, total_ids, context=context):    
            log_f.write('%s|%s\n' % (
                product.default_code, 
                product.lst_price,
                ))    
        log_f.close()
        return True

    def update_all_product_extra_label_field(self, cr, uid, ids, context=None):
        ''' Update all product
        '''
        if context is None:
            context = {}
            ctx = {}
        else:    
            ctx = context.copy()
        ctx['product_selection'] = 'all'
        self.update_product_extra_label_field(cr, uid, ids, context=ctx)
        
    def update_product_extra_label_field(self, cr, uid, ids, context=None):
        ''' Update extra fields product
        '''
        if context is None:
            context = {}
            
        all_product = context.get('product_selection', False) == 'all'    

        # Pool used:
        line_pool = self.pool.get('sale.order.line')
        product_pool = self.pool.get('product.product')
        
        # Only order:
        if all_product:
            _logger.info('Force description all product')
            # All product:    
            product_ids = product_pool.search(cr, uid, [
                ('structure_id', '!=', False),
                ('default_code', '!=', False),
                ], context=context)        
        else: # only order product:
            _logger.info('Force description only product order')
            line_ids = line_pool.search(cr, uid, [
                ('order_id.state', 'in', ('draft', 'cancel', 'sent', 'done')),
                ], context=context)

            product_ids =  []
            for line in line_pool.browse(cr, uid, line_ids, context=context):
                product_id = line.product_id.id
                if line.product_id.structure_id and line.product_id.default_code:
                    if product_id not in product_ids:
                        product_ids.append(product_id)
                else:
                    _logger.error(
                        'Product no structure/code %s' % line.product_id.name)
            
        ctx = context.copy()
        ctx['update_only_field'] = ('label_frame', 'label_fabric_color')
        ctx['log_file'] = '/home/administrator/photo/log/speech.csv'

        for product in product_pool.browse(
                cr, uid, product_ids, context=context):   
            product_pool.generate_name_from_code(
                cr, uid, [product.id], context=ctx)
            _logger.info('Update label field: %s' % product.default_code)
            
        return True
        
    """        
    def import_exclude_list(self, cr, uid, ids, context=None):
        ''' Import exclude list from file easy
        '''
        exclude_pool = self.pool.get('product.codebar.exclude')

        filename = '/home/administrator/photo/xls/ean/barcode.xls'

        try:
            WB = xlrd.open_workbook(filename)
        except:
            raise osv.except_osv(
                _('Error XLSX'), 
                _('Cannot read XLS file: %s' % filename),
                )

        # Load current list:                
        exclude_ids = exclude_pool.search(cr, uid, [], context=context)        
        exclude_proxy = exclude_pool.browse(
            cr, uid, exclude_ids, context=context)
        exclude = [item.name for item in exclude_proxy]
        
        fixed = '8017882'
        WS = WB.sheet_by_index(0)
        for row in range(1, WS.nrows):
            ean13_s = WS.cell(row, 4).value
            ean13_p = WS.cell(row, 5).value
            
            if ean13_s and ean13_s.startswith(fixed):
                code = ean13_s[7:12]
                if code not in exclude:
                    exclude.append(code)

            if ean13_p and ean13_p.startswith(fixed):
                code = ean13_p[7:12]
                if code not in exclude:
                    exclude.append(code)
        for name in exclude:
            try:
                exclude_pool.create(cr, uid, {
                    'name': name,
                    }, context=context)            
            except:
                _logger.warning('Yet present: %s' % name)
        return True

    """
    def import_exclude_list(self, cr, uid, ids, context=None):
        ''' Import exclude list from file easy
        '''
        def generate_code(value):
            ''' Add extra char
            '''
            import barcode
            EAN = barcode.get_barcode_class('ean13')
            if len(value) == 13:
                return value
            elif len(value) == 12:
                ean13 = EAN(value)
                return ean13.get_fullcode()
            else:
                return ''

        exclude_pool = self.pool.get('product.codebar.exclude')

        filename = '/home/administrator/photo/xls/ean/doppi.xls'
        product_pool = self.pool.get('product.product')
        try:
            WB = xlrd.open_workbook(filename)
        except:
            raise osv.except_osv(
                _('Error XLSX'), 
                _('Cannot read XLS file: %s' % filename),
                )

        # Load current list:                
        exclude_ids = exclude_pool.search(cr, uid, [], context=context)        
        exclude_proxy = exclude_pool.browse(
            cr, uid, exclude_ids, context=context)
        exclude = [item.name for item in exclude_proxy]
        
        fixed = '8017882'
        WS = WB.sheet_by_index(0)

        import pdb; pdb.set_trace()
        for row in range(0, WS.nrows):
            # Read fields
            default_code = WS.cell(row, 0).value
            try:
                ean13_s = generate_code('%s' % int(WS.cell(row, 0).value))
            except:
                ean13_s = ''
                
            #try:
            #    ean13_p = generate_code('%s' % int(WS.cell(row, 2).value))
            #except:
            #    ean13_p = ''
                        
            if ean13_s and ean13_s.startswith(fixed):
                code = ean13_s[7:12]
                if code not in exclude:
                    exclude.append(code)

            #if ean13_p and ean13_p.startswith(fixed):
            #    code = ean13_p[7:12]
            #    if code not in exclude:
            #        exclude.append(code)
        import pdb; pdb.set_trace()            
        for name in exclude:
            try:
                exclude_pool.create(cr, uid, {
                    'name': name,
                    }, context=context)            
            except:
                _logger.warning('Yet present: %s' % name)
        return True

    def check_ean_easylabel(self, cr, uid, ids, context=None):
        ''' Check file XLS for double
        '''
        # ---------------------------------------------------------------------
        # Utility:
        # ---------------------------------------------------------------------
        def generate_code(value):
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

        # Pool used:
        product_pool = self.pool.get('product.product')        
        
        # ---------------------------------------------------------------------
        #                Open XLS document (first WorkSheet):
        # ---------------------------------------------------------------------
        # Parameters:
        filename = '/home/administrator/photo/xls/barcode.xls'                
        filelog = '/home/administrator/photo/xls/barcode_log.xlsx'
        max_check = 10000
        
        _logger.info('Start import from path: %s' % filename)
        
        try:
            WB = xlrd.open_workbook(filename)
            WS = WB.sheet_by_index(0)
        except:
            raise osv.except_osv(
                _('Import file: %s') % filename, 
                _('Error opening XLS file: %s' % (sys.exc_info(), )),
                )

        # ---------------------------------------------------------------------
        #                Read barcode database
        # ---------------------------------------------------------------------
        ean_db = {} # XLS read database
        ean13_db = {} # Database for write in product
        
        # Check database:
        ean1_db = []
        ean4_db =  []
        
        # Error database:
        error = {
            'yet_present': [],
            'double_code': [],
            'ean1_not_present': [],
            'ean4_not_present': [],
            'double_ean_1_4': [],
            'double_ean1': [],
            'double_ean4': [],
            'different_1_4': [],
            'different_4_1': [],
            'odoo_product_not_present': [],
            'odoo_product_double_code': [],
            }

        for line in range(1, max_check): # jump header
            try:                
                row = WS.row(line)
            except:
                _logger.info('Break read at line: %s' % line)
                break
            
            try:    
                # Read data:
                default_code = row[0].value
                if default_code in ean_db:
                    error['yet_present'].append(default_code)
                    continue

                try:
                    ean1 = generate_code('%s' % int(row[1].value))
                except:
                    ean1 = False                    
                try:
                    ean4 = generate_code('%s' % int(row[2].value))
                except:
                    ean4 = False    
                
                # Create ean13 database single or pack (1 code only):
                if default_code[12:13] == 'S':
                    if not ean1:
                        error['ean1_not_present'].append(default_code)
                    single = True
                    ean13 = ean1
                else:
                    if not ean4:
                        error['ean4_not_present'].append(default_code)
                    single = False
                    ean13 = ean4
                
                # 0. Check double ean for 1 and 4 code!    
                if ean13 in ean13_db.values():
                    error['double_ean_1_4'].append(ean13)
                else:    
                    ean13_db[default_code] = ean13
                
                # 1. check double code:
                
                if default_code in ean_db:
                    error['double_code'].append(default_code)
                else:    
                    ean_db[default_code] = (ean1, ean4) # save 2 ean code
                                    
                if single:
                    # 2. check double ean 1
                    if ean1 in ean1_db:
                        error['double_ean1'].append(ean1)
                    else:
                        ean1_db.append(ean1)                    
                else:
                    # 3. check double ean 4
                    if ean4 in ean4_db:
                        error['double_ean4'].append(ean4)
                    else:
                        ean4_db.append(ean4)
            except:
                _logger.error('Error: %s [%s]' % (
                    default_code, sys.exc_info()))

        # 4. Check difference code in 1 for pack and 4 for single        
        for default_code, eans in ean_db.iteritems():
            # Is single:
            if default_code[12:13] == 'S':
                pack = default_code[:12].strip()
                if pack in ean_db:                
                    if eans[0] != ean_db[pack][0]:
                        error['different_1_4'].append(default_code)                    
            # Is pack:
            else:
                single = ean_db.get('%-12sS' % default_code)
                if single in ean_db:                
                    if eans[0] != ean_db[single][0]:
                        error['different_4_1'].append(default_code)

        # ---------------------------------------------------------------------                
        # Write EAN in database (check also presence and double)
        # ---------------------------------------------------------------------
        WB = xlsxwriter.Workbook(filelog)
        WS = WB.add_worksheet('ODOO')
        WS.write(0, 0, 'Codice')
        WS.write(0, 1, 'Q. x pack')
        WS.write(0, 2, 'Uso')
        WS.write(0, 3, 'Commento')
        WS.write(0, 4, 'EAN singolo')
        WS.write(0, 5, 'EAN pack')

        counter = 1
        for default_code, eans in ean_db.iteritems():
            (ean1, ean4) = eans
            
            product_ids = product_pool.search(cr, uid, [
                ('default_code', '=', default_code)], context=context)	
            if product_ids:            
                if len(product_ids) > 1:
                    error['odoo_product_double_code'].append(default_code)
                    
                product_proxy = product_pool.browse(
                    cr, uid, product_ids, context=context)[0]
                q_x_pack = product_proxy.q_x_pack
                if q_x_pack == 1:
                    ean13 = ean1
                    comment = 'Singolo'
                    if default_code[12:13] != 'S':
                        comment = 'Singolo (errore codice senza S)'
                else:
                    ean13 = ean4
                    comment = 'Pacco'
                    if default_code[12:13] == 'S':
                        comment = 'Pacco (errore codice con S)'

                # Write log:                    
                WS.write(counter, 0, default_code) 
                WS.write(counter, 1, q_x_pack)
                WS.write(counter, 2, ean13)
                WS.write(counter, 3, comment)
                WS.write(counter, 4, ean1)
                WS.write(counter, 5, ean4)
                counter += 1        
                    
                # TODO enable when correct:   
                #product_pool.write(cr, uid, product_ids, {
                #    'ean13': ean13,
                #    }, context=context)
            else:
                error['odoo_product_not_present'].append(default_code)

        # ---------------------------------------------------------------------                
        # Log error:
        # ---------------------------------------------------------------------                
        for page, log in error.iteritems():
            WS = WB.add_worksheet(page)
            if not log:
                continue
            counter = 0
            for item in log:
                WS.write(counter, 0, item)
                counter += 1        
        return True
        
    def force_first_supplier(self, cr, uid, ids, context=None):
        ''' Force first supplier
        '''
        product_pool = self.pool.get('product.product')        
        product_ids = product_pool.search(cr, uid, [], context=context)            
        first_supplier = {}

        for product in product_pool.browse(
                cr, uid, product_ids, context=context):
            old_date = False
            supplier_id = False
            for seller in product.seller_ids:
                for pl in seller.pricelist_ids:
                    current_date = pl.write_date
                    if not old_date or old_date < current_date:
                        old_date = current_date
                        supplier_id = seller.name.id
            if supplier_id:
                first_supplier[product.id] = supplier_id
        
        # Loop for write:
        for product_id, seller_id in first_supplier.iteritems():
            product_pool.write(cr, uid, product_id, {
                'first_supplier_id': seller_id,
                }, context=context)                
        return True
        
    def export_mailing_list(self, cr, uid, ids, context=None):
        ''' Export mailing list
        '''
        def write_xls_line(line):
            ''' Write line in correct WS with mode selection
            '''
            col = 0
            for item in line:
                self.WS.write(self.counter, col, item)
                col += 1
        
            self.counter += 1
            return 
        
        # XLS generate file:
        xls = '/home/administrator/photo/output/mailing.xlsx'
        _logger.warning('Log file: %s' % xls)
        WB = xlsxwriter.Workbook(xls)

        self.WS = WB.add_worksheet('Partner')
        self.counter = 0
            
        # Write Header line:
        write_xls_line((
            'Ciente', 'Fornitore', 'Azienda', 'Indirizzo', 'Camcard', 'Email',
            'Opt out', 'Feedback', 
            'Nome', 'Citta', 'Nazione', 'Email', 'Sito', 'Telefono',
            'Cat. Stat.', 'Newsletter', 'Tipo', 'Zona',
            ))
        
        partner_pool = self.pool.get('res.partner')
        partner_ids = partner_pool.search(cr, uid, 
            [], order='name', context=context)
        for partner in partner_pool.browse(
                cr, uid, partner_ids, context=context):
            write_xls_line((
                
                'X' if partner.customer else '',
                'X' if partner.supplier else '',
                'X' if partner.is_company else '',
                'X' if partner.is_address else '',
                'X' if partner.camcard_text else '',
                'X' if partner.email else '',
                
                'X' if partner.news_opt_out else '',
                partner.news_feedback_id.name if \
                    partner.news_feedback_id else '',
                
                partner.name,
                partner.city,
                partner.country_id.name,
                partner.email,
                partner.website,
                partner.phone,
                partner.statistic_category_id.name,
                partner.newsletter_category_id.name,
                partner.type_id.name,
                partner.zone_id.name,                
                ))
            
        return True
    def lavoration_inventory_modification(self, cr, uid, ids, context=None):
        ''' Export data from lavoration
        '''
        out_file = '/home/administrator/photo/output/lavoration_problem.csv'
        out_f = open(out_file, 'w')
        _logger.warning('Export lavoration problem: %s' % out_file)
        
        pick_pool = self.pool.get('stock.picking')
        pick_ids = pick_pool.search(cr, uid, [], order='name', context=context)
        
        out_f.write('Doc.|Create|Write|Date|Code|Qty|INV.\n')
        for pick in pick_pool.browse(cr, uid, pick_ids, context=context):
            for line in pick.sl_quants_ids:
                row = '%s|%s|%s|%s|%s|%s|%s\n' % (
                    # Header:
                    pick.name,
                    pick.create_date,
                    pick.write_date,
                    pick.date,
                    
                    # Line:
                    line.product_id.default_code,
                    line.qty,                    
                    line.product_id.mx_start_qty,
                    )
                out_f.write(row.replace('.', ','))
        _logger.warning('End export lavoration')
        out_f.close()
        return True
    
    def inventory_to_reset(self, cr, uid, ids, context=None):
        ''' Check error during operation on bom
        '''
        out_file = '/home/administrator/photo/log/product_to_reset'
        out_file_jump = '/home/administrator/photo/log/product_to_reset_jumped'
        
        out_f = open(out_file, 'w')
        out_jump = open(out_file_jump, 'w')
        
        # Pool used:
        product_pool = self.pool.get('product.product')

        # Check HW bon link:
        product_ids = product_pool.search(cr, uid, [
            ('default_code', 'not in', product_present),                     
            ], context=context)

        for product in product_pool.browse(
                cr, uid, product_ids, context=context):                
            if not product.default_code or product.default_code[:1] not in \
                    '1234567890G':                    
                out_jump.write('%s|0\n' % product.default_code)
                continue     
                    
            out_f.write('%s|0\n' % product.default_code)
        out_f.close()
        out_jump.close()        
