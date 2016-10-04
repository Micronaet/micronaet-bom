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
        'bom_id': fields.many2one('mrp.bom', 'BOM', required=True,
            domain=[('bom_category', '=', 'parent')]),
        'quantity': fields.integer('Total', required=True),        
        # XXX always explode half worked
        'note': fields.text('Note'),
        }

class PurchaseOrder(orm.Model):
    """ Model name: PurchaseOrder
    """
    
    _inherit = 'purchase.order'
    
    def explode_bom_purchase_line(self, cr, uid, ids, context=None):
        ''' Generate order depend on final component for bom selected
        '''
        return True
    
    _columns = {
        'explode_bom': fields.boolean('Explode from BOM'),
        'explode_bom_calc': fields.text('Explode calc'), 
        'explode_bom_error': fields.text('Explode error'), 
        
        'explode_bom_ids': fields.one2many(
            'purchase.order.bom', 'bom_id', 
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
