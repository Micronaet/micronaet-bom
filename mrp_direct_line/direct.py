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

class SaleOrderLine(orm.Model):
    ''' Link line for stats
    '''
    _inherit = 'sale.order.line'

    # -------------------------------------------------------------------------
    # Button event:    
    # -------------------------------------------------------------------------
    def working_mark_as_done(self, cr, uid, ids, context=None):
        ''' Print single label
        '''
        return self.write(cr, uid, ids, {
            'working_done': True,
            }, context=context)

    def working_print_single_label(self, cr, uid, ids, context=None):
        ''' Print single label
        '''    
        return True

    _columns = {
        'working_line_id': fields.many2one(
            'mrp.production.stats', 'Working on'),
        'working_sequence': fields.integer('Working seq.'),
        'working_qty': fields.integer('Working q.'),
        'working_done': fields.boolean('Done'),
        }
    
class MrpProductionStat(orm.Model):
    ''' Statistic data
    '''
    _inherit = 'mrp.production.stats'

    # -------------------------------------------------------------------------
    # Button event:    
    # -------------------------------------------------------------------------
    def working_mark_as_done(self, cr, uid, ids, context=None):
        ''' Print single label
        '''
        return self.write(cr, uid, ids, {
            'working_done': True,
            }, context=context)

    def working_print_all_label(self, cr, uid, ids, context=None):
        ''' Print single label
        '''    
        return True

    _columns = {
        'working_ids': fields.one2many(
            'sale.order.line', 'working_line_id', 'Working line',
            help='Sale order line working on this day'),
        'working_done': fields.boolean('Done'),            
        }
    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
