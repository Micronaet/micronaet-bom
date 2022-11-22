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


class StockPickingDevice(orm.Model):
    """ Model name: StockPickingDevice
    """

    _name = 'stock.picking.device'
    _description = 'Lavoration device'

    _columns = {
        'name': fields.char('Device', size=64, required=True),
        'note': fields.text('Note'),
        }


class ResCompany(orm.Model):
    """ Model name: ResCompany
    """

    _inherit = 'res.company'

    def _get_company_browse(self, cr, uid, context=None):
        """ Browse first company for parameter read
        """
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
        # For show direct SL lavoration when confirmed:
        'linked_cl_stock_move_id': fields.many2one(
            'stock.move', 'Link CL linked move', ondelete='set null'),
        }


class StockMove(orm.Model):
    """ Model name: StockMove
    """

    _inherit = 'stock.move'

    # Fields function:
    def _get_linked_sl_status(self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate
        """
        res = {}

        for item in self.browse(cr, uid, ids, context=context):
            res[item.id] = ''
            if item.picking_id.state == 'done':  # SL movement:
                for sl in item.linked_sl_stock_move_id_ids:
                    res[item.id] += '%s: %s\n' % (
                        sl.product_id.default_code or '??',
                        sl.product_qty,
                        )
            else:  # show BOM:
                for bom in item.product_id.half_bom_ids:
                    if item.remove_obtainable and bom.obtainable_component:
                        _logger.warning('Remove obtainable component: %s' %
                                        bom.product_id.default_code)
                        continue
                    res[item.id] += '%s: %s\n' % (
                        bom.product_id.default_code or '??',
                        bom.product_qty * (
                            item.product_uom_qty + item.product_fail_qty),
                        )
        return res

    _columns = {
        'product_fail_qty': fields.float(
            'Damaged',
            digits_compute=dp.get_precision('Product Unit of Measure')),

        'linked_sl_stock_move_id_ids': fields.one2many(
            'stock.move', 'linked_cl_stock_move_id',
            'Linked SL movements'),
        'linked_sl_status': fields.function(
            _get_linked_sl_status, method=True,
            type='text', string='SL movement',
            store=False),
        'remove_obtainable': fields.boolean(
            'No ricavabili',
            help='Rimuove dalla distinta i componenti ricavabili'),
        }


class MRPLavoration(orm.Model):
    """ Manage lavoration as a new object
    """
    _inherit = 'stock.picking'

    def get_material_info_from_mrp(self, cr, uid, ids, context=None):
        """ Extract info from MRP linked
        """
        info = ''
        current_proxy = self.browse(cr, uid, ids, context=context)[0]

        res = {}
        for line in current_proxy.linked_mrp_id.order_line_ids:
            product = line.product_id
            if product in res:
                res[product] += line.product_uom_qty
            else:
                res[product] = line.product_uom_qty
        for product, qty in res.iteritems():
            for hw in product.dynamic_bom_line_ids:
                _logger.info('Category: %s' % hw.category_id.name)
                if hw.category_id.department == 'cut':
                    info += '''
                        <tr class='table_bf'>
                            <td>%s</td>
                            <td>%s</td>
                            <td>%s</td>
                            <td>%s</td>
                        </tr>
                        ''' % (
                            product.default_code,
                            qty,
                            hw.category_id.name,
                            hw.product_id.default_code,
                            )
        info = _('''
            <style>
                    .table_mrp {
                         border:1px 
                         padding: 3px;
                         solid black;
                     }
                    .table_mrp td {
                         border:1px 
                         solid black;
                         padding: 3px;
                         text-align: center;
                     }
                    .table_mrp th {
                         border:1px 
                         solid black;
                         padding: 3px;
                         text-align: center;
                         background-color: grey;
                         color: white;
                     }
                </style>
            <table class='table_mrp'>
                <tr class='table_bf'>
                    <th>Code</th>
                    <th>Q.</th>
                    <th>Category</th>
                    <th>Component</th>                    
                </tr>%s</table>''') % info
        return self.write(cr, uid, ids, {
            'mrp_material_info': info,
            }, context=context)

    def force_done(self, cr, uid, ids, context=None):
        """ Confirm lavoration
        """
        # Pool used:
        move_pool = self.pool.get('stock.move')
        quant_pool = self.pool.get('stock.quant')

        pick_proxy = self.browse(cr, uid, ids, context=context)[0]

        # Read parameters:
        company_proxy = self.pool.get('res.company')._get_company_browse(
            cr, uid, context=context)

        sl_type = company_proxy.sl_mrp_lavoration_id
        sl_type_id = sl_type.id or False

        stock_location = sl_type.default_location_src_id.id or False
        mrp_location = sl_type.default_location_dest_id.id or False

        origin = 'CL-LAV-%s' % pick_proxy.name

        cl_date = pick_proxy.date  # XXX use CL date for all!

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
            self.write(cr, uid, sl_id, {
                'picking_type_id': sl_type_id,
                'state': 'done',
                'date': cl_date,
                'min_date': cl_date,
                'origin': _('SL from %s') % origin,
                'is_mrp_lavoration': False,  # SL is hidden
                # TODO no more fields?
                }, context=context)

        else:
            sl_id = self.create(cr, uid, {
                'picking_type_id': sl_type_id,
                'state': 'done',
                'date': cl_date,
                'min_date': cl_date,
                'origin': _('SL from %s') % origin,
                'is_mrp_lavoration': False,  # SL is hidden
                # TODO no more fields?
                }, context=context)

        # ---------------------------------------------------------------------
        # (Re) create movement for SL depend on CL:
        # ---------------------------------------------------------------------
        for load in pick_proxy.move_lines:
            product = load.product_id
            load_qty = load.product_qty
            load_fail_qty = load_qty + load.product_fail_qty

            # Load quats materials:
            quant_pool.create(cr, uid, {
                'in_date': cl_date,  # TODO document date??
                'cost': 0.0, # TODO
                'location_id': stock_location,
                'product_id': product.id,
                'qty': load_qty,
                'lavoration_link_id': pick_proxy.id,
                }, context=context)

            for component in product.half_bom_ids:
                if load.remove_obtainable and component.obtainable_component:
                    _logger.warning('Remove obtainable stock move: %s' %
                                    component.product_id.default_code)
                    continue

                product = component.product_id
                unload_qty = component.product_qty * load_fail_qty
                if unload_qty <= 0.0:
                    continue  # jump line

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
                    'state': 'done',  # confirmed, available
                    'origin': origin,  # CL lavoration
                    'date': cl_date,
                    'date_expected': cl_date,
                    'name': _('SL-LAV-%s') % pick_proxy.name,
                    'linked_cl_stock_move_id': load.id,  # link CL move
                    # 'display_name': 'SL: %s' % line_proxy.product_id.name,
                    # 'product_uom_qty',
                    # 'product_uos',
                    # 'product_uos_qty',
                    }, context=context)

                # Unload quats materials:
                quant_pool.create(cr, uid, {
                    'in_date': cl_date,
                    'cost': 0.0,  # TODO
                    'location_id': stock_location,
                    'product_id': product.id,
                    'qty': - unload_qty,
                    'lavoration_link_id': pick_proxy.id,
                    }, context=context)

        # ---------------------------------------------------------------------
        # Update CL move status:
        # ---------------------------------------------------------------------
        move_ids = move_pool.search(cr, uid, [
            ('picking_id', '=', ids[0])], context=None)
        move_pool.write(cr, uid, move_ids, {
            # 'partner_id':
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
        """ Confirm Job
        """
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

    # Default function:
    def _get_picking_type_id(self, cr, uid, context=None):
        """ Check value from startup method in context
        """
        if context is None:
            context = {}
        if not context.get('open_mrp_lavoration', False):
            return False
        company_proxy = self.pool.get('res.company')._get_company_browse(
            cr, uid, context=context)
        return company_proxy.cl_mrp_lavoration_id.id or False
        # TODO check error on false

    _columns = {
        'total_work': fields.float('Tot. work H.', digits=(16, 3)),
        'total_prepare': fields.float('Tot. prepare H.', digits=(16, 3)),
        'total_stop': fields.float('Tot. stop H.', digits=(16, 3)),
        'workers': fields.char('Workers', size=64),
        'is_mrp_lavoration': fields.boolean('Is Lavoration'),  # todo remove!!!
        'device_id': fields.many2one('stock.picking.device', 'Device'),

        # Override:
        'picking_type_id': fields.many2one(
            'stock.picking.type', 'Picking Type',
            states={
                'done': [('readonly', True)],
                'cancel': [('readonly', True)],
                }, required=True),
        'linked_mrp_id': fields.many2one('mrp.production', 'MRP linked'),
        'mrp_material_info': fields.text('MRP material info', readonly=True),
        'linked_sl_id': fields.many2one('stock.picking', 'SL linked'),
        'sl_quants_ids': fields.one2many(
            'stock.quant', 'lavoration_link_id', 'Stock quants',),
        'dep_mode': fields.selection([
            ('cut', 'Cut department'),
            ('workshop', 'Workshop department'),
            ], 'Department mode', readonly=True),
        }

    _defaults = {
        'picking_type_id': lambda s, cr, uid, ctx: s._get_picking_type_id(
            cr, uid, ctx),
        }


class MrpProduction(orm.Model):
    """ Model name: MrpProduction
    """

    _inherit = 'mrp.production'

    _columns = {
        'linked_picking_ids': fields.one2many(
            'stock.picking', 'linked_mrp_id',
            'Cut'),
    }
