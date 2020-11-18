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


class StockPicking(orm.Model):
    """ Model name: Stock Picking extra link to MRP
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
    _columns = {
        'linked_mrp_id': fields.many2one(
            'mrp.production', 'Linked MRP'),
        'mrp_material_info': fields.text('MRP material info', readonly=True),
        }


class MrpProduction(orm.Model):
    """ Model name: Mrp Production
    """

    _inherit = 'mrp.production'

    _columns = {
        'cl_sl_ids': fields.one2many(
            'stock.picking', 'linked_mrp_id',
            'Linked lavoration'),
        }
