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


class PurchaseOrderBOM(orm.Model):
    """ Model name: PurchaseOrderBOM
    """    
    
    _name = 'purchase.order.bom'
    _description = 'Purchase from BOM'
    _rec_name = 'bom_id'
    
    def explode_hw_purchase_line(self, cr, uid, ids, context=None):
        ''' Recal single component
        '''
        assert len(ids) == 1, 'Works only with one record a time'
        half_id = ids[0]
        
        half_proxy = self.browse(cr, uid, half_id, context=context)
        # TODO 
        line_ids = line_pool.search(cr, uid, [
            ('explode_bom_id', '=', half_id),
            ], context=context)
        line_pool.unlink(cr, uid, line_ids, context=context)

        order_proxy = half_proxy.purchase_id
        order_id = half_proxy.purchase_id.id
        partner = half_proxy.purchase_id.partner_id
        
        half_quantity = half_proxy.quantity_order        
        for item in half_proxy.product_id.half_bom_ids:
            # Create purchase order line:
            item_quantity = half_quantity * item.product_qty
            
            item_data = line_pool.onchange_product_id(
                cr, uid, ids, 
                order_proxy.pricelist_id.id, 
                item.product_id.id, 
                item_quantity, 
                item.product_id.uom_id.id, 
                partner.id, 
                order_proxy.date_order, 
                partner.property_account_position.id,
                # Line property:
                #order_proxy.date_planned, 
                #name, 
                #price_unit=False, 
                #state='draft', 
                context=context,
                ).get('value', {})

            # TODO VAT not loaded!!!!
            if 'taxes_id' in item_data:
                item_data['taxes_id'] = [(6, 0, item_data['taxes_id'])]

            if item_data:                      
                item_data.update({
                    'order_id': order_id,
                    'explode_bom_id': half_id,
                    'product_id': item.product_id.id,
                    })
                line_pool.create(cr, uid, item_data, context=context)
                
        
        return True
    
    _columns = {
        # Link:
        'purchase_id': fields.many2one('purchase.order', 'Order'),
        'bom_id': fields.many2one('mrp.bom', 'BOM', readonly=True),
        'parent_quantity': fields.integer('Parent total', readonly=True), 

        'product_id': fields.many2one('product.product', 'Halfworked', 
            readonly=True),
        'quantity': fields.integer('Total', readonly=True),        
        'quantity_order': fields.integer('Order'),
        
        'explode_bom_calc': fields.text('Explode calc', readonly=True), 
        'explode_bom_error': fields.text('Explode error', readonly=True), 

        'note': fields.text('Note'),
        }

class PurchaseOrder(orm.Model):
    """ Model name: PurchaseOrder
    """
    
    _inherit = 'purchase.order'
    
    def explode_bom_purchase_line(self, cr, uid, ids, context=None):
        ''' Generate order depend on final component for bom selected
        '''
        assert len(ids) == 1, 'Works only with one record a time'
        
        # Pool used:
        line_pool = self.pool.get('purchase.order.line')
        bom_line_pool = self.pool.get('purchase.order.bom')
        bom_pool = self.pool.get('mrp.bom')
        
        order_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        # Field used:
        order_id = order_proxy.id
        total = order_proxy.quantity
        partner = order_proxy.partner_id        
        load_bom_id = order_proxy.load_bom_id.id
        
        # Remove previous line (only generated line):
        remove_ids = bom_line_pool.search(cr, uid, [
            ('purchase_id', '=', order_id), # this purchase order
            ('bom_id', '=', load_bom_id), # this load bom child
            ], context=context)        
        if remove_ids:
            remove_line_ids = line_pool.search(cr, uid, [
                ('order_id', '=', order_id), # this purchase order
                ('explode_bom_id', 'in', remove_ids),
                ], context=context)    
            line_pool.unlink(cr, uid, remove_line_ids, context=context)              
            bom_line_pool.unlink(cr, uid, remove_ids, context=context)
            
        # Generate current lines:
        #bom_data = {} # {ID: [calc, error]}
        
        # Search hw in bom selected
        for half in order_proxy.load_bom_id.bom_line_ids:
            if not half.product_id.half_bom_ids:
                # No subcomponent, jump this HW
                # TODO log error
                continue
                
            # Create record in purchase.order.bom
            half_quantity = total * half.product_qty
            half_id = bom_line_pool.create(cr, uid, {
                # Link:
                'purchase_id': order_id,
                'bom_id': load_bom_id,
                'parent_quantity': total, 
                
                # Data:
                'product_id': half.product_id.id,
                'quantity': half_quantity,
                'quantity_order': half_quantity, # init setup
                
                #'explode_bom_calc': False, 
                #'explode_bom_error': False,
                #'note': False,
                }, context=context)
            
            for item in half.product_id.half_bom_ids:
                # Create purchase order line:
                item_quantity = half_quantity * item.product_qty
                
                item_data = line_pool.onchange_product_id(
                    cr, uid, ids, 
                    order_proxy.pricelist_id.id, 
                    item.product_id.id, 
                    item_quantity, 
                    item.product_id.uom_id.id, 
                    partner.id, 
                    order_proxy.date_order, 
                    partner.property_account_position.id,
                    # Line property:
                    #order_proxy.date_planned, 
                    #name, 
                    #price_unit=False, 
                    #state='draft', 
                    context=context,
                    ).get('value', {})

                # TODO VAT not loaded!!!!
                if 'taxes_id' in item_data:
                    item_data['taxes_id'] = [(6, 0, item_data['taxes_id'])]

                if item_data:                      
                    item_data.update({
                        'order_id': order_id,
                        'explode_bom_id': half_id,
                        'product_id': item.product_id.id,
                        })
                    line_pool.create(cr, uid, item_data, context=context)
                    
                    #bom_data[bom.id][0] += _(
                    #    '%s: %s x %s x %s = %s  [%s]\n') % (
                    #        half.product_id.default_code or 'cod. ?',
                    #        bom.quantity,
                    #        half.product_qty,
                    #        item.product_qty,
                    #        qty,
                    #        item.product_id.default_code or 'cod. ?',
                    #        )
                #else:    
                #    bom_data[bom.id][0] += _(
                #        '%s No data to write') % bom.product_id.name
                
                               
        # Write error for bom load: # XXX no more fields delete!!
        #for bom_id, data in bom_data.iteritems():
        #    bom_line_pool.write(cr, uid, bom_id, {
        #        'explode_bom_calc': data[0],
        #        'explode_bom_error': data[1] or False,
        #        }, context=context)
        return True
    
    _columns = {
        # Data for explode wizard:
        'load_bom_id': fields.many2one(
            'mrp.bom', 'Load BOM'),
        'quantity': fields.integer('Total'),
        'explode_bom_calc': fields.text('Explode calc.', readonly=True), 
        'explode_bom_error': fields.text('Explode error', readonly=True), 

        'explode_bom': fields.boolean('Explode from BOM'),
        'explode_bom_ids': fields.one2many(
            'purchase.order.bom', 'purchase_id', 
            'Explode BOM'),
        }

class PurchaseOrder(orm.Model):
    """ Model name: PurchaseOrder
    """
    
    _inherit = 'purchase.order.line'
        
    _columns = {
        'explode_bom_id': fields.many2one(
            'purchase.order.bom', 'Explode BOM', ondelete='cascade'),            
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
