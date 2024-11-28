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
import pdb
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


class StockMove(orm.Model):
    """ Model name: Stock move
    """

    _inherit = 'stock.move'

    def _get_last_price_control_costs(self, product):
        """ Return product requested last price
        """
        last_date = False
        last_price = 0.0
        for seller in product.seller_ids:
            for price in seller.pricelist_ids:
                if not last_date or last_date < price.date_quotation:
                    last_price = price.price
                    last_date = price.date_quotation
        if last_price:
            return last_price, last_date
        else:
            return 0.0, ''

    def _get_purchase_product_last_date(self, cr, uid, context=None):
        """ Generate database for last purchase
        """

        res = {}
        domain = []

        from_date = datetime.now()
        line_ids = self.search(cr, uid, [
            ('state', '=', 'done'),
            ('picking_id.origin', '=ilike', 'OF%'),
            # ('origin', '=ilike', 'OF%'),  # not all origin present!
            ], context=context)

        for line in sorted(
                self.browse(cr, uid, line_ids, context=context),
                key=lambda x: x.picking_id.date,
                reverse=True):
            product = line.product_id
            if not product or product.id in res:
                continue

            line_price = line.price_unit
            if line_price:
                # Read from OF purchase order line:
                line_date = (line.picking_id.date or '')[:10]
                line_uom = line.product_uom.name
                line_qty = line.product_uom_qty
            else:
                # Read from product cost management:
                line_price, line_date = self._get_last_price_control_costs(
                    product)
                line_uom = product.uom_id.name or ''
                line_qty = 'NO OF!'

            # [acq. 2022-03-08 m 891.0: costo un. 3.338]
            res[product.id] = \
                'CAR %s - SCAR %s ' \
                '[acq. %s %s %s: costo un. %s]' % (
                    product.old_tcar or 0,
                    product.old_tscar or 0,
                    line_date,
                    line_uom,
                    line_qty,
                    line_price,
                    )
        to_date = datetime.now()
        gap = int((to_date - from_date).seconds / 60.0)
        _logger.info('Total purchase product: %s [time %s]' % (
            len(line_ids), gap))
        return res
