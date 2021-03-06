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
import logging
from openerp.osv import fields, osv, expression, orm

_logger = logging.getLogger(__name__)


class SaleOrder(orm.Model):
    """ Model name: SaleOrder
    """
    _inherit = 'sale.order'

    # -------------------------------------------------------------------------
    #                               UTILITY
    # -------------------------------------------------------------------------
    def get_component_in_product_order_open(
            self, cr, uid, logfile=False, context=None):
        """ Check open order and return list of product present
            (for line not closed)
            chose logfile if report need to log operation
        """
        line_pool = self.pool.get('sale.order.line')

        # ---------------------------------------------------------------------
        # Database:
        # ---------------------------------------------------------------------
        data = {
            # Data database
            'product': [],  # database for product
            # 'component': [], # database for component

            # TODO
            # 'order': [], # order header
            # 'line': [], # order line

            # Check error database:
            'no_product': [],
            'no_structure': [],
            # 'no_component': [],
            }

        # Search open order:
        line_ids = line_pool.search(cr, uid, [
            ('order_id.state', 'not in', ('cancel', 'sent', 'draft')),
            ('order_id.pricelist_order', '=', False),
            # remove no parcels product:
            ('product_id.exclude_parcels', '=', False),

            ('order_id.mx_closed', '=', False), # order open
            ('mx_closed', '=', False), # line open
            # Remove product without col!
            ], context=context)

        forecasted_ids = line_pool.search(cr, uid, [
            ('order_id.forecasted_production_id', '!=', False),
            ('order_id.forecasted_production_id.state', 'not in', (
                'done', 'cancel')),
            ])
        line_ids.extend(forecasted_ids)  # no double FC is draft mode

        for line in line_pool.browse(cr, uid, line_ids, context=context):
            product = line.product_id  # Readability:

            # -----------------------------------------------------------------
            # Check no product:
            # -----------------------------------------------------------------
            if not product:
                data['no_product'].append(line)  # browse line no product
                continue

            structure = product.structure_id  # Readability

            # -----------------------------------------------------------------
            # Save for explode in report:
            # -----------------------------------------------------------------
            if product not in data['product']:
                data['product'].append(product)

            # -----------------------------------------------------------------
            # Check structure:
            # -----------------------------------------------------------------
            if not structure and product not in data['no_structure']:
                data['no_structure'].append(product)

        return data
