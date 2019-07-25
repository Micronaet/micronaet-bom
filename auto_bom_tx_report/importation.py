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
import base64
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

class PurchaseOrderXLSX(orm.Model):
    """ Model name: PurchaseOrderXLSX
    """    
    _name = 'purchase.order.xlsx'
    _description = 'Imported order'
    _rec_name = 'name'
    _order = 'name'

    # --------------------
    # Wizard button event:
    # --------------------
    def extract_line_in_tree(self, cr, uid, ids, context=None):
        ''' Extract element in list
        '''
        model_pool = self.pool.get('ir.model.data')
        view_id = model_pool.get_object_reference(
            cr, uid, 'auto_bom_tx_report', 'view_order_line_tree')[1]
        current_proxy = self.browse(cr, uid, ids, context=context)[0]
        line_ids = [item.id for item in current_proxy.line_ids]
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Righe'),
            'view_type': 'form',
            'view_mode': 'tree',
            #'res_id': 1,
            'res_model': 'purchase.order.xlsx.line',
            'view_id': view_id,
            'views': [(view_id, 'tree')],
            'domain': [('id', 'in', line_ids)],
            'context': context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }
            
    def action_create_order(self, cr, uid, ids, context=None):
        ''' Create purchase order:
        '''
        
        # Pool used:
        purchase_pool = self.pool.get('purchase.order')
        pol_pool = self.pool.get('purchase.order.line')
        location_pool = self.pool.get('stock.location')
        
        today = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        purchase_db = {} # list of purchase order per partner
        for line in self.browse(cr, uid, ids, context=context)[0].line_ids:
            partner = line.partner_id
            if not partner.id:
                raise osv.except_osv(
                    _('No partner'), 
                    _('Set all partner for create invoice!'),
                    )
                
            # -----------------------------------------------------------------
            # Header:
            # -----------------------------------------------------------------
            if partner.id not in purchase_db:
                # Location: (XXX find better mode!)
                location_ids = location_pool.search(cr, uid, [
                    ('name', '=', 'Stock'),
                    ], context=context)

                res = purchase_pool.onchange_partner_id(cr, uid, False, 
                    partner.id, context=context)
                data = res.get('value', {})
                    
                # Generate header:
                data.update({
                    'partner_id': partner.id,
                    'date_order': today,
                    'location_id': location_ids[0],
                    })
                purchase_id = purchase_pool.create(cr, uid, data, 
                    context=context)
                purchase_db[partner.id] = purchase_pool.browse(
                    cr, uid, purchase_id, context=context)
                    
            # -----------------------------------------------------------------
            # Details:
            # -----------------------------------------------------------------
            purchase = purchase_db[partner.id]
            data_line = {}

            # onchange product_id:
            purchase_id = purchase.id
            pricelist_id = purchase.pricelist_id.id
            product_id = line.product_id.id
            partner_id = purchase.partner_id.id
            name = purchase.name
            fiscal_position = purchase.fiscal_position.id
            date_order = purchase.date_order
            date_planned = line.deadline
            qty = line.quantity
            uom_id = line.product_id.uom_id.id
            
            res = pol_pool.onchange_product_id(cr, uid, False, 
                pricelist_id, product_id, 0, False, partner_id, date_order,
                fiscal_position, date_planned, False, False, 'draft', 
                context=context)
            data_line.update(res.get('value', {}))
                        
            # onchange product_qty:
            res = pol_pool.onchange_product_id(cr, uid, False,
                pricelist_id, product_id, qty, uom_id, partner_id, date_order, 
                fiscal_position, date_planned, name, False, 'draft', 
                context=context)
            data_line.update(res.get('value', {}))
            
            # onchange uom:
            res = pol_pool.onchange_product_uom(cr, uid, False,
                pricelist_id, product_id, qty, uom_id, partner_id, date_order,
                fiscal_position, date_planned, name, False, 'draft', 
                context=context) 
            data_line.update(res.get('value', {}))

            if 'taxes_id' in data_line:
                taxes_id = [(6, 0, data_line['taxes_id'])]
                
            data_line.update({
                'product_id': product_id,
                'order_id': purchase_id,
                'taxes_id': taxes_id,
                # TODO link link with file?
                })
            
            pol_pool.create(cr, uid, data_line, context=context)
                    
        # Link purchase order to import record
        purchase_ids = [po.id for po in purchase_db.values()]
        purchase_pool.write(cr, uid, purchase_ids, {
            'xlsx_id': ids[0],
            }, context=context)
        return True

    def action_import_leadtime_lot(self, cr, uid, ids, context=None):
        ''' Event for button done force update lead lot
        '''
        if context is None: 
            context = {}
        
        context['update_lead_lot'] = True
        context['update_inventory_category'] = True
        context['obsolete'] = True
        
        return self.action_import_order(cr, uid, ids, context=context)

    def action_import_order(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        if context is None: 
            context = {}        
        
        update_lead_lot = context.get('update_lead_lot', False)
        update_inventory_category = context.get(
            'update_inventory_category', False)
        update_obsolete = context.get('obsolete', False)
        
        # Pool used:
        product_pool = self.pool.get('product.product')
        line_pool = self.pool.get('purchase.order.xlsx.line') 
        inventory_pool = self.pool.get('product.product.inventory.category')
        
        inventory_db = {}
        if update_inventory_category:
            inventory_ids = inventory_pool.search(cr, uid, [], context=context)
            for item in inventory_pool.browse(cr, uid, inventory_ids, 
                    context=context):
                inventory_db[item.name] = item.id
            
        current_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        # ---------------------------------------------------------------------
        # Save file passed:
        # ---------------------------------------------------------------------
        if not current_proxy.file:
            raise osv.except_osv(
                _('No file:'), 
                _('Please pass a XLSX file for import order'),
                )
        b64_file = base64.decodestring(current_proxy.file)
        now = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        filename = '/tmp/tx_%s.xlsx' % now.replace(':', '_').replace('-', '_')
        f = open(filename, 'wb')
        f.write(b64_file)
        f.close()
        
        xslx_id = current_proxy.id
        month_db = {
            # Previous year:
            2: '09', 3: '10', 4: '11', 5: '12',
            
            # Next year:
            6: '01', 7: '02', 8: '03', 9: '04', 10: '05', 11: '06', 
            12: '07', 13: '08',
            }
            
        # Parameters:    
        row_start = 0            
        month_current = datetime.now().month
        year_current =  datetime.now().year
        if month_current in [9, 10, 11, 12]:
            year_a = year_current
            year_b = year_current + 1
        else: # 1 > 8
            year_a = year_current - 1
            year_b = year_current
            
        # ---------------------------------------------------------------------
        # Load force name (for web publish)
        # ---------------------------------------------------------------------
        try:
            WB = xlrd.open_workbook(filename)
        except:
            raise osv.except_osv(
                _('Error XLSX'), 
                _('Cannot read XLS file: %s' % filename),
                )
        
        # ---------------------------------------------------------------------        
        # Loop on all pages:
        # ---------------------------------------------------------------------        
        today = now[:10]
        for ws_name in WB.sheet_names():
            if ws_name == 'Non usati':
                _logger.warning('Jump page: %s' % ws_name)
                continue
                
            WS = WB.sheet_by_name(ws_name)   
            _logger.warning('Read page: %s' % ws_name)

            pos = -1
            error = ''
            for row in range(row_start, WS.nrows):
                pos += 1
                if pos == 1: 
                    # ---------------------------------------------------------
                    # Read product code:
                    # ---------------------------------------------------------
                    default_code = WS.cell(row, 0).value
                    _logger.info('Find material: %s' % default_code)

                    product_id = False           
                      
                    # Manage code error:
                    if not default_code:
                        _logger.error('No material code')
                        error += 'Riga: %s > No codice materiale\n' % row
                        continue

                    # Search product:
                    product_ids = product_pool.search(cr, uid, [
                        ('default_code', '=', default_code)
                        ], context=context)
                        
                    # Manage product error:
                    if not product_ids: 
                        _logger.error(
                            'No product with code: %s' % default_code)
                        # FATAL ERROR (maybe file not in correct format, raise:
                        raise osv.except_osv(
                            _('Errore controllare anche il formato del file'), 
                            _('Non trovato il codice prodotto: %s' % (
                                default_code)),
                            )
                        error += 'Riga: %s > No prodotto: %s\n' % (
                            row, default_code)
                        continue
                        
                    # TODO manage warning more than one product
                    elif len(product_ids) > 1:
                        _logger.error('More material code: %s' % default_code)
                        error += 'Riga: %s > Codice doppio: %s\n' % (
                            row, default_code)
                        pass # TODO multi code
                    
                    product_id = product_ids[0]    
                    product_proxy = product_pool.browse(cr, uid, product_id, 
                        context=context)

                    # ---------------------------------------------------------
                    # Search supplier:
                    # ---------------------------------------------------------
                    # 1. Procurements:
                    if product_proxy.seller_ids:
                        partner_id = product_proxy.seller_ids[0].name.id
                    
                    # 2. First supplier
                    elif product_proxy.first_supplier_id:
                        partner_id = product_proxy.first_supplier_id.id
                    else:   
                        partner_id = False                    
                        
                elif pos == 6: # order qty                
                    # ---------------------------------------------------------
                    # Read quantity and get deadline:
                    # ---------------------------------------------------------
                    for col in range(2, 14):
                        quantity = WS.cell(row, col).value
                        
                        try:
                            # TODO replace . on , ?
                            quantity = float(quantity)
                        except:
                            _logger.warning(
                                'Problem convert float / empty: %s' % quantity)
                            quantity = 0.0
                            
                        if not quantity:
                            continue
                        
                        month = month_db[col]
                        day = '01' # TODO Parameterize (wizard data)
                        if month in ['09', '10', '11', '12']:
                            year = year_a
                        else:
                            year = year_b

                        # Note: Deadline minimun today!
                        deadline = '%s-%s-%s' % (year, month, day)                        
                        if deadline < today:
                            deadline = today
                        
                        line_pool.create(cr, uid, {
                            'xlsx_id': ids[0],
                            'product_id': product_id,
                            'partner_id': partner_id,
                            'quantity': quantity,
                            'deadline': deadline,
                            }, context=context)

                    # Extra data:
                    if update_lead_lot:
                        product_pool.write(cr, uid, product_id, {
                            'leadtime': WS.cell(row, 14).value,
                            'purchase_lot_block': WS.cell(row, 15).value, 
                            }, context=context)

                    if update_inventory_category and WS.cell(row, 16).value:                        
                        inventory_category_id = inventory_db.get(
                            WS.cell(row, 16).value, False)
                        if inventory_category_id:
                            product_pool.write(cr, uid, product_id, {
                                'inventory_category_id': inventory_category_id,
                                }, context=context)

                    if update_obsolete:
                        obsolete_text = (WS.cell(row, 17).value or '').upper()
                        if obsolete_text in 'XS':
                            product_pool.write(cr, uid, product_id, {
                                'status': 'obsolete',
                                }, context=context)
                                
                elif pos in (7, 8) and not WS.cell(row, 0).value:
                    _logger.warning('Reset pos, row: %s' % row)
                    pos = -1            

        # Update status of import record
        _logger.info('Imported: %s' % filename)
        return self.write(cr, uid, ids, {
            'mode': 'imported',
            'file': False, # reset file for clean database!
            'error': error,
            }, context=context)
    
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'file': fields.binary('XLSX file', filters=None),
        'mode': fields.selection([
            ('draft', 'Draft'),
            ('imported', 'Imported'),
            ('created', 'Created'),            
            ], 'Mode'),
        'error': fields.text('Errore'),
        }
    
    _defaults = {
       'name': lambda *a: _('Imported: %s') % datetime.now().strftime(
            DEFAULT_SERVER_DATE_FORMAT),
        'mode': lambda *x: 'draft',
        }

class PurchaseOrderXLSXLine(orm.Model):
    """ Model name: PurchaseOrderXLSX Line
    """
    
    _name = 'purchase.order.xlsx.line'
    _description = 'Imported order line'
    _rec_name = 'product_id'
    _order = 'sequence'
    
    _columns = {
        'sequence': fields.integer('Sequence'),
        'product_id': fields.many2one(
            'product.product', 'Product'),
        'uom_id': fields.related(
            'product_id', 'uom_id', 
            type='many2one', relation='product.uom', 
            string='UM'),
        'deadline': fields.date('Deadline'),
        'partner_id': fields.many2one('res.partner', 'Supplier'),
        'quantity': fields.float('Q.ty', digits=(16, 3)),
        'xlsx_id': fields.many2one(
            'purchase.order.xlsx', 'Import wizard', 
            required=False),
        }

class PurchaseOrder(orm.Model):
    """ Model name: PurchaseOrder
    """
    
    _inherit = 'purchase.order'

    _columns = {
        'xlsx_id': fields.many2one(
            'purchase.order.xlsx', 'Import record', 
            required=False),
        }
    
class PurchaseOrderXLSX(orm.Model):
    """ Model name: PurchaseOrderXLSX
    """    
    _inherit = 'purchase.order.xlsx'
    
    _columns = {
        'line_ids': fields.one2many(
            'purchase.order.xlsx.line', 'xlsx_id', 'Line'),
        'purchase_ids': fields.one2many(
            'purchase.order', 'xlsx_id', 'Purchase order'),
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
