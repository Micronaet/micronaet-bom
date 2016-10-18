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

class MrpBom(orm.Model):
    """ Model name: Bom line
    """    
    _inherit = 'mrp.bom'
    
    # Used for generate default when start from BOM
    _columns = {
        'relative_id': fields.many2one(
            'product.product', 'Relative product'),
        }

class MrpBomLine(orm.Model):
    """ Model name: Bom line
    """
    
    _inherit = 'mrp.bom.line'
    
    _columns = {
        'relative_id': fields.many2one(
            'product.product', 'Relative product'),
        }

class ProductProduct(orm.Model):
    """ Model name: ProductProduct
    """
    
    _inherit = 'product.product'

    # -------------------------------------------------------------------------
    # Button event:
    # -------------------------------------------------------------------------
    def create_product_relative_bom(self, cr, uid, ids, context=None):
        ''' Create BOM for relative         
        '''        
        assert len(ids) == 1, 'Works only with one record a time'
        bom_pool = self.pool.get('mrp.bom')
        
        product_proxy = self.browse(cr, uid, ids, context=context)[0]
        bom_id = bom_pool.create(cr, uid, {
            'product_tmpl_id': product_proxy.product_tmpl_id.id,
            'product_id': product_proxy.id,
            'bom_category': product_proxy.relative_type, # XXX no none!
            'product_qty': 1.0,
            'code': product_proxy.default_code,
            'type': 'normal',
            'product_uom': product_proxy.uom_id.id,
            'relative_id': product_proxy.id,
            }, context=context)
            
        return self.write(cr, uid, ids, {
            'relative_bom_id': bom_id,
            }, context=context)
    
        
    _columns = {
        'relative_type': fields.selection([
            ('none', 'None'),
            ('half', 'Halfworked'),
            ('parent', 'Parent'),
            ], 'Relative type')
            
        'relative_bom_id': fields.many2one(
            'mrp.bom', 'Relative BOM', readonly=True),
        'relative_bom_ids': fields.one2many(
            'mrp.bom.line', 'relative_id', 
            'Relative component'),
        }
        
    _defaults = {
       'relative_type': lambda *x: 'none',
       }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
