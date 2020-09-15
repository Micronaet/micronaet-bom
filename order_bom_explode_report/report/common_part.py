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
    
    # -------------------------------------------------------------------------
    # Utility for report generation:
    # -------------------------------------------------------------------------         
    # TODO To be removed:
    def mrp_order_line_to_produce(self, line):
        ''' Get order line to produce depend on OC-B-Delivery (and assigned)
        '''
        ready_qty = line.product_uom_maked_sync_qty
        if ready_qty >= line.delivered_qty:
            return (
                # Remain to make:
                line.product_uom_qty - ready_qty,
                # Remain to delivery:
                ready_qty - line.delivered_qty,
                )
        else:    
            return (
                # Remain to make:
                line.product_uom_qty - line.delivered_qty,
                # Remain to delivery:
                0.0,
                )

    def mrp_order_line_to_produce_assigned(self, line):
        ''' Get order line to produce depend on OC-B-Delivery (and assigned)
            TODO New function will replace previous
        '''
        ready_qty = line.product_uom_maked_sync_qty + line.mx_assigned_qty
        if ready_qty >= line.delivered_qty:
            remain = line.product_uom_qty - ready_qty
            return (
                # Remain to make:
                remain if remain > 0.0 else 0.0,
                # Remain to delivery:
                ready_qty - line.delivered_qty,
                )
        else:    
            return (
                # Remain to make:
                line.product_uom_qty - line.delivered_qty,
                # Remain to delivery:
                0.0,
                )

