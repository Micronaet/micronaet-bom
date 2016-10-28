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
    
    _columns = {
        'enable_mrp_lavoration': fields.boolean('Enable lavoration'),
        'sl_mrp_lavoration_id': fields.many2one(
            'stock.picking.type', 'SL Lavoration'),
        'cl_mrp_lavoration_id': fields.many2one(
            'stock.picking.type', 'CL Lavoration'),
        }


class MRPLavoration(orm.Model):  
    """ Manage lavoration as a new object
    """
    _inherit = 'stock.picking'
           
    def _get_is_mrp_lavoration(self, cr, uid, context=None):
        ''' Check value from startup method in context
        '''       
        if context is None:
            context = {}
        return context.get('open_mrp_lavoration', False)

    _columns = {
        'is_mrp_lavoration': fields.boolean('Is Lavoration'),
        }       
    
    #_defaults = {
    #    'is_mrp_lavoration': lambda s, cr, uid, ctx: s._get_is_mrp_lavoration(
    #        cr, uid, ctx),
    #    }
            
    '''def mrp_generate_sl_cl_movement(self, cr, uid, sol_ids, context=None):
        """ Generic function used for create / update stock move,
            CL and SL, used from create and write method            
        """
        assert len(ids) == 1, 'Works only with one record a time'
        
        if context is None:
            context = {}
            
        # Pool used:
        move_pool = self.pool.get('stock.move')
        quant_pool = self.pool.get('stock.quant')
        company_pool = self.pool.get('res.company')

        # Parameter for location:
        company_ids = company_pool.search(cr, uid, [], context=context)
        company_proxy = company_pool.browse(cr, uid, company_ids, 
            context=context)[0]

        # TODO remove stock elements (use type)?:
        stock_location = company_proxy.stock_location_id.id
        mrp_location = company_proxy.stock_mrp_location_id.id
        
        if company_proxy.stock_report_mrp_in_ids: # XXX only first
            mrp_type_in = company_proxy.stock_report_mrp_in_ids[0].id
        else:
            mrp_type_in = False    
            
        if company_proxy.stock_report_mrp_out_ids:    
            mrp_type_out = company_proxy.stock_report_mrp_out_ids[0].id
        else:
            mrp_type_out = False
        
        if not(mrp_location and stock_location):
            raise osv.except_osv(
                _('Error'), 
                _('Set up in company location for stock and mrp1!'))
        
        line_proxy = self.browse(cr, uid, sol_ids, context=context)[0]
        
        # Test if is a stock load family:
        try:
            if line_proxy.mrp_id.bom_id.product_tmpl_id.no_stock_operation:
                _logger.warning('No load stock family, do nothing!')
                return True
        except:        
            _logger.warning('Error test no load stock family!')
            # continune unload stock as default
        
        # Get pick document linked to MRP production:
        mrp_picking_in = pick_pool.get_mrp_picking(
            cr, uid, line_proxy.mrp_id, 'cl', mrp_type_in, 
            context=context)
        mrp_picking_out = pick_pool.get_mrp_picking(
            cr, uid, line_proxy.mrp_id, 'sl', mrp_type_out, 
            context=context)

        # get product BOM for materials:
        bom_proxy = self._search_bom_for_product(cr, uid, 
            line_proxy.product_id.id, context=context)

        if persistent:
            maked_qty = line_proxy.product_uom_force_qty or 0.0
        else:
            maked_qty = line_proxy.product_uom_maked_sync_qty or 0.0

        # -------------------------------
        # Unlink all stock move (always):
        # -------------------------------
        if not persistent: # XXX domain persistent status for delete?
            move_ids = move_pool.search(cr, uid, [
                ('production_sol_id', '=', line_proxy.id),
                ('persistent', '=', False),
                ], context=context)
            if move_ids:
                # Set to draft:
                move_pool.write(cr, uid, move_ids, {
                    'state': 'draft',
                    }, context=context)
                # delete:    
                move_pool.unlink(cr, uid, move_ids, context=context)

            # -----------------------
            # Unlink all stock quant:
            # -----------------------
            quant_ids = quant_pool.search(cr, uid, [
                ('production_sol_id', '=', line_proxy.id),
                ('persistent', '=', False),
                ], context=context)
            if quant_ids:
                # Set to draft:
                quant_pool.unlink(cr, uid, quant_ids, context=context)

        if not maked_qty:   
            return True
        
        # Create SL move:
        if bom_proxy:
            # Unload materials:
            for bom in bom_proxy.bom_line_ids:
                unload_qty = bom.product_qty * maked_qty
                if unload_qty <= 0.0:
                    continue # jump line
                    
                # Move create:    
                move_pool.create(cr, uid, {
                    'picking_id': mrp_picking_out,
                    'production_load_type': 'sl',
                    'location_dest_id': mrp_location,
                    'location_id': stock_location,
                    'picking_type_id': mrp_type_out,
                    'product_id': bom.product_id.id,
                    'product_uom_qty': unload_qty, 
                    'product_uom': bom.product_id.uom_id.id,

                    #'product_uom_qty',
                    #'product_uos',
                    #'product_uos_qty',
                    'production_sol_id': line_proxy.id,
                    'state': 'done', # confirmed, available
                    'date_expected': datetime.now().strftime(
                        DEFAULT_SERVER_DATE_FORMAT),
                    'origin': line_proxy.mrp_id.name,
                    'display_name': 'SL: %s' % line_proxy.product_id.name,
                    'name': 'SL: %s' % line_proxy.product_id.name,
                    'persistent': persistent,
                    #'warehouse_id',

                    #'weight'
                    #'weight_net',
                    #'group_id'
                    #'production_id'
                    #'product_packaging'                    
                    #'company_id'
                    #'date':
                    #date_expexted'
                    #'note':,
                    #'partner_id':
                    #'price_unit',
                    #'priority',.                    
                    }, context=context)
                 
                # Quants create:    
                quant_pool.create(cr, uid, {
                    'in_date': datetime.now().strftime(
                        DEFAULT_SERVER_DATETIME_FORMAT),
                    'cost': 0.0, # TODO
                    'location_id': stock_location,
                    'product_id': bom.product_id.id,
                    'qty': - unload_qty, 
                    #'product_uom': bom.product_id.uom_id.id,
                    'production_sol_id': line_proxy.id,
                    'persistent': persistent,
                    }, context=context)   
        else:
            # No bom error!!
            #_logger.error('BOM not found sql_import for product: %s' % (
            #    line_proxy.product_id.default_code or ''))
            raise osv.except_osv(
                _('Error'), 
                _('BOM not found sql_import for product: %s' % (
                    line_proxy.product_id.default_code or '')))
        
        # Load end product:    
        # TODO
        if not persistent:
            move_pool.create(cr, uid, {
                'picking_id': mrp_picking_in,
                'production_load_type': 'cl',
                'picking_type_id': mrp_type_in,
                'location_dest_id': stock_location,
                'location_id': mrp_location,
                'product_id': line_proxy.product_id.id,
                'product_uom_qty': maked_qty, 
                'product_uom': line_proxy.product_id.uom_id.id,
                'production_sol_id': line_proxy.id,
                #'product_uom_qty',
                #'product_uos',
                #'product_uos_qty',
                'state': 'done', # confirmed, available
                'date_expected': datetime.now().strftime(
                    DEFAULT_SERVER_DATE_FORMAT),
                'origin': line_proxy.mrp_id.name,
                'display_name': 'CL: %s' % line_proxy.product_id.name,
                'name': 'CL: %s' % line_proxy.product_id.name,
                #'warehouse_id',
                #'picking_type_id',

                #'weight'
                #'weight_net',
                #'picking_id'
                #'group_id'
                #'production_id'
                #'product_packaging'                    
                #'company_id'
                #'date':
                #date_expexted'
                #'note':,
                #'partner_id':
                #'price_unit',
                #'priority',.                    
                }, context=context)
                
            # Quants create:    
            quant_pool.create(cr, uid, {
                'in_date': datetime.now().strftime(
                    DEFAULT_SERVER_DATETIME_FORMAT),
                'cost': 0.0, # TODO
                'location_id': stock_location,
                'product_id': line_proxy.product_id.id,
                'qty': maked_qty, 
                'production_sol_id': line_proxy.id,
                }, context=context)   
        return True     '''   
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
