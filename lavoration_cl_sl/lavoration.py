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

class ResCompany(orm.Model):
    """ Model name: ResCompany
    """
    
    _inherit = 'res.company'
    
    def _get_company_browse(self, cr, uid, context=None):
        ''' Browse first company for parameter read
        '''
        company_ids = self.search(cr, uid, [], context=context)
        return self.browse(cr, uid, company_ids, context=context)[0]        
        
    _columns = {
        'enable_mrp_lavoration': fields.boolean('Enable lavoration'),
        'sl_mrp_lavoration_id': fields.many2one(
            'stock.picking.type', 'SL Lavoration'),
        'cl_mrp_lavoration_id': fields.many2one(
            'stock.picking.type', 'CL Lavoration'),
        }

class StockQuant(orm.Model):
    """ Model name: Stock quant
    """    
    _inherit = 'stock.quant'
    
    _columns = {
        'lavoration_link_id': fields.many2one(
            'stock.picking', 'Link to CL lavoration', ondelete='cascade'),
        }

class StockMove(orm.Model):
    """ Model name: StockMove
    """    
    _inherit = 'stock.move'
    
    _columns = {
        'linked_cl_stock_move_id': fields.many2one(
            'stock.move', 'Link CL linked move', ondelete='set null'),
        }
        
class StockMove(orm.Model):
    """ Model name: StockMove
    """
    
    _inherit = 'stock.move'
    
    # Fields function:
    def _get_linked_sl_status(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate 
        '''
        res = {}
        #for item in self.browse(cr, uid, ids, context=context):
        #    res[item.id] = ''
        #    for sl in item.linked_sl_stock_move_ids:
        #        res[item.id] += '%s: %s\n' % (
        #            sl.product_id.default_code or '??',
        #            sl.product_qty,
        #            )
        return res

    _columns = {
        'linked_sl_stock_move_ids': fields.one2many(
            'stock.move', 'linked_cl_stock_move_id', 
            'Link SL move'),
        'linked_sl_status': fields.function(
            _get_linked_sl_status, method=True, 
            type='text', string='SL movement', 
            store=False),                         
        }

class MRPLavoration(orm.Model):  
    """ Manage lavoration as a new object
    """
    _inherit = 'stock.picking'
    
    def force_done(self, cr, uid, ids, context=None):
        ''' Confirm lavoration
        '''
        # Pool used:
        move_pool = self.pool.get('stock.move')
        quant_pool = self.pool.get('stock.quant')

        pick_proxy = self.browse(cr, uid, ids, context=context)[0]

        # Read paremeters:
        company_proxy = self.pool.get('res.company')._get_company_browse(
            cr, uid, context=context)        
            
        sl_type = company_proxy.sl_mrp_lavoration_id
        sl_type_id = sl_type.id or False
        stock_location = sl_type.default_location_src_id.id or False
        mrp_location = sl_type.default_location_dest_id.id or False 
        origin = 'CL-LAV-%s' % pick_proxy.name
        now = datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)
        # TODO better MRP, now is procurements type?

        if not(mrp_location and stock_location):
            raise osv.except_osv(
                _('Error'), 
                _('Set up in company location for stock and mrp1!'))
        
        # ---------------------------------------------------------------------
        # Create / Update SL picking:
        # ---------------------------------------------------------------------
        if pick_proxy.linked_sl_id:
            sl_id = pick_proxy.linked_sl_id.id
        else:
            sl_id = self.create(cr, uid, {
                'picking_type_id': sl_type_id,
                'state': 'done',
                'date': now,
                'origin': origin,    
                #TODO
                }, context=context)
                
        # ---------------------------------------------------------------------
        # (Re) create movement for SL depend on CL:
        # ---------------------------------------------------------------------
        for load in pick_proxy.move_lines:
            product = load.product_id
            load_qty = load.product_qty
            
            # Load quats materials:
            quant_pool.create(cr, uid, {
                'in_date': now,
                'cost': 0.0, # TODO
                'location_id': stock_location,
                'product_id': product.id,
                'qty': load_qty,
                'lavoration_link_id': pick_proxy.id,
                }, context=context)
            
            for component in product.half_bom_ids:
                product = component.product_id
                unload_qty = component.product_qty * load_qty
                if unload_qty <= 0.0:
                    continue # jump line

                # Unload with stock move:
                move_pool.create(cr, uid, {
                    'picking_id': sl_id,
                    'linked_cl_stock_move_id': component.id,
                    'location_id': stock_location,
                    'location_dest_id': mrp_location,
                    'picking_type_id': sl_type_id,
                    'product_id': product.id,
                    'product_uom_qty': unload_qty, 
                    'product_uom': product.uom_id.id,
                    'state': 'done', # confirmed, available
                    'origin': origin, # CL lavoration
                    'date_expected': now,
                    'name': _('SL-LAV-%s') % pick_proxy.name,
                    #'display_name': 'SL: %s' % line_proxy.product_id.name,
                    #'product_uom_qty',
                    #'product_uos',
                    #'product_uos_qty',
                    }, context=context)
                    
                # Unload quats materials:
                quant_pool.create(cr, uid, {
                    'in_date': now,
                    'cost': 0.0, # TODO
                    'location_id': stock_location,
                    'product_id': product.id,
                    'qty': - unload_qty,
                    'lavoration_link_id': pick_proxy.id,
                    }, context=context)
        
        # ---------------------------------------------------------------------
        # Udate CL move status:
        # ---------------------------------------------------------------------
        move_ids = move_pool.search(cr, uid, [
            ('picking_id', '=', ids[0])], context=None)
        move_pool.write(cr, uid, move_ids, {
            #'partner_id': 
            'state': 'done',
            }, context=context)
            
        # ---------------------------------------------------------------------
        # Update header status:
        # ---------------------------------------------------------------------
        return self.write(cr, uid, ids, {
            'state': 'done',
            'linked_sl_id': sl_id,
            }, context=context)

    def force_draft(self, cr, uid, ids, context=None):
        ''' Confirm lavoration
        '''
        pick_proxy = self.browse(cr, uid, ids, context=context)[0]
        # Delete load movements:
        
        # Move:
        move_pool = self.pool.get('stock.move')
        quant_pool = self.pool.get('stock.quant')

        # ---------------------------------------------------------------------
        # Delete all quant movement:
        # ---------------------------------------------------------------------
        quant_ids = quant_pool.search(cr, uid, [
            ('lavoration_link_id', '=', ids[0]),
            ], context=context)
        if quant_ids:
            quant_pool.unlink(cr, uid, quant_ids, context=context)  

        # ---------------------------------------------------------------------
        # Delete previous SL movements:
        # ---------------------------------------------------------------------
        sl_id = pick_proxy.linked_sl_id.id

        if sl_id:
            # Search SL lined:
            line_ids = move_pool.search(cr, uid, [
                ('picking_id', '=', sl_id),
                ], context=context)
            # Set draft before delete:
            move_pool.write(cr, uid, line_ids, {
                'state': 'draft',
                }, context=context)
            # Delete move:
            move_pool.unlink(cr, uid, line_ids, context=context)

        # ---------------------------------------------------------------------
        # Draft CL movements and header:
        # ---------------------------------------------------------------------
        # Movement:
        stock_ids = move_pool.search(cr, uid, [
            ('picking_id', '=', ids[0])], context=None)
        move_pool.write(cr, uid, stock_ids, {
            'state': 'draft'}, context=context)
            
        # Header:        
        return self.write(cr, uid, ids, {
            'state': 'draft',
            }, context=context)
            
    def _get_is_mrp_lavoration(self, cr, uid, context=None):
        ''' Check value from startup method in context
        '''       
        if context is None:
            context = {}
        return context.get('open_mrp_lavoration', False)

    # Default function:
    def _get_picking_type_id(self, cr, uid, context=None):
        ''' Check value from startup method in context
        '''       
        if context is None:
            context = {}
        if not context.get('open_mrp_lavoration', False):   
            return False
        company_proxy = self.pool.get('res.company')._get_company_browse(
            cr, uid, context=context)        
        return company_proxy.cl_mrp_lavoration_id.id or False
        # TODO check error on false

    _columns = {
        'is_mrp_lavoration': fields.boolean('Is Lavoration'),
        # Override:
        'picking_type_id': fields.many2one(
            'stock.picking.type', 'Picking Type', 
            states={
                'done': [('readonly', True)], 
                'cancel': [('readonly', True)],
                }, required=True),
        'linked_sl_id': fields.many2one('stock.picking', 'SL linked'),
        }       
    
    _defaults = {
        #'is_mrp_lavoration': lambda s, cr, uid, ctx: s._get_is_mrp_lavoration(
        #    cr, uid, ctx),
        'picking_type_id': lambda s, cr, uid, ctx: s._get_picking_type_id(
            cr, uid, ctx),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
