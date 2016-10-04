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
    
    _columns = {
        'purchase_id': fields.many2one('purchase.order', 'Order'),
        'bom_id': fields.many2one('mrp.bom', 'BOM', required=True),
        'quantity': fields.integer('Total', required=True),        
        # XXX always explode half worked
        'note': fields.text('Note'),
        'explode_bom_calc': fields.text('Explode calc', readonly=True), 
        'explode_bom_error': fields.text('Explode error', readonly=True), 
        }

class PurchaseOrder(orm.Model):
    """ Model name: PurchaseOrder
    """
    
    _inherit = 'purchase.order'
    
    def get_bom_for_half_worked(self, cr, uid, product_id, context=None):
        ''' Search bom for product passed
        '''
        bom_pool = self.pool.get('mrp.bom')
        return = bom_pool.search(cr, uid, [
            ('product_id', '=', product_id),
            ('bom_category', '=', 'half'),
            ], context=context)
                    

    def explode_bom_purchase_line(self, cr, uid, ids, context=None):
        ''' Generate order depend on final component for bom selected
        '''
        assert len(ids) == 1, 'Works only with one record a time'
        
        line_pool = self.pool.get('purchase.order.line')
        bom_pool = self.pool.get('mrp.bom')
        
        order_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        # Remove previous line (only generated line):
        remove_ids = [
            line.id for line in order_proxy.order_line if line.explode_bom_id]
        line_pool.unlink(cr, uid, remove_ids, context=context)
            
        # Generate current lines:
        error = {}
        
        for bom in order_proxy.explode_bom_ids:
            error[bom.id] = ''            
            for half in bom.bom_line_ids:
                bom_ids = self.get_bom_for_half_worked(
                    cr, uid, product_id, context=context)

                if not bom_ids:
                    error[bom.id] += _(
                        'No BOM for component %s\n') % \
                            half.product_id.default_code
                elif len(bom_ids) > 1: # XXX warning?
                    error[bom.id] += _(
                        'Multi BOM for component %s\n') % \
                            half.product_id.default_code
                else:   
                    bom_proxy = bom_pool.browse(
                        cr, uid, bom_ids, context=context)[0]
                        
                    # Generate final product from half worked bom:
                    for item in bom_proxy.bom_line_ids:
                        qty = bom.quantity * item.product_qty
                     
                        data = self.onchange_product_id(
                            cr, uid, ids, order_proxy.pricelist_id.id, 
                            item.product_id.id, qty, 
                            item.product_id.uom_id, order_proxy.partner_id.id, 
                            order_proxy.date_order, 
                            order_proxy.fiscal_position_id.id,
                            order_proxy.date_planned, 
                            #name, 
                            #price_unit=False, 
                            #state='draft', 
                            context=context,
                            ).get('value', {})
                        if data:                      
                            # TODO log event
                            data.update({
                                'order_id': ids[0],
                                #'product_id': ,
                                })
                            line_pool.create(cr, uid, data, context=context)
                               
        # Write error for bom load:
        for bom_id, error in error.iteritems():
            pass # TODO
        return True
    
    _columns = {
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
        'explode_bom_id': fields.many2one('purchase.order.bom', 'Explode BOM'),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
