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
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID
from openerp import tools
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT,
    DATETIME_FORMATS_MAP,
    float_compare)

_logger = logging.getLogger(__name__)


class CreateNewMrpLineDayWizard(orm.TransientModel):
    """ Wizard for new line day
    """
    _name = 'mrp.production.new.line.day.wizard'

    # --------------------
    # Wizard button event:
    # --------------------
    def action_done(self, cr, uid, ids, context=None):
        """ Event for button done
        """
        if context is None:
            context = {}

        # Pool used:
        stats_pool = self.pool.get('mrp.production.stats')
        sol_pool = self.pool.get('sale.order.line')

        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]

        # Create the statistic event mrp.production.stats
        stats_id = stats_pool.create(cr, uid, {
            'date': wiz_proxy.date,
            'mrp_id': wiz_proxy.mrp_id.id,
            'workcenter_id': wiz_proxy.line_id.id,
            'total': 0,
            # 'working_done': False,
            }, context=context)

        # ---------------------------------------------------------------------
        # Migrate sale order line in this production day:
        # ---------------------------------------------------------------------
        sol_update = []

        for sol in wiz_proxy.mrp_id.order_line_ids:
            # Check if delivered qty
            if sol.delivered_qty > sol.product_uom_maked_sync_qty:
                remain = sol.product_uom_qty - sol.delivered_qty
            else:
                remain = sol.product_uom_qty - sol.product_uom_maked_sync_qty

            # Check if assigned qty:
            assigned_qty = sol.mx_assigned_qty
            if assigned_qty:
                remain = remain - assigned_qty

            if remain <= 0:
                continue  # no production
            sol_update.append((sol.id, remain))
        if sol_update:
            for item_id, remain in sol_update:
                sol_pool.write(cr, uid, item_id, {
                    'working_line_id': stats_id,
                    'working_qty': remain,
                    'working_ready': False,  # reset every time
                    }, context=context)

        # Create first status point for pallet management:
        stats_pool.generate_material_planned_bom(
            cr, uid, [stats_id], context=context)
        stats_pool.working_new_pallet(cr, uid, [stats_id], context=context)

        # Save total at start up:
        working_start_total = stats_pool.get_current_production_number(
            cr, uid, [stats_id], context=context)
        stats_pool.write(cr, uid, [stats_id], {
            'working_start_total': working_start_total,
            }, context=context)

        # ---------------------------------------------------------------------
        # Return in production management for this day:
        # ---------------------------------------------------------------------
        return {
            'type': 'ir.actions.act_window',
            'name': _('Day production'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': stats_id,
            'res_model': 'mrp.production.stats',
            # 'view_id': view_id, # False
            'views': [(False, 'form')],
            'domain': [],
            'context': context,
            'target': 'current',  # 'new'
            'nodestroy': False,
            }

    _columns = {
        'date': fields.date('Day', required=True),
        'line_id': fields.many2one(
            'mrp.workcenter', 'Line', required=True),
        'mrp_id': fields.many2one(
            'mrp.production', 'Production', required=True),
        }

    _defaults = {
        'date': lambda *x: datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
        }
