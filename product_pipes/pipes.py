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

class MRPBomLine(orm.Model):
    """ Model name: Bom line
    """    
    _inherit = 'mrp.bom.line'
     
    _columns = {
        'length_cut': fields.float('Length cut', digits=(16, 2), 
            help='Part for cut pipe that will be wasted'), 
        'waste_cut': fields.float('Waste cut', digits=(16, 2), 
            help='Part for cut pipe that will be wasted'), # not used for now
        'part_x_pipe': fields.integer('Part per pipe',
            help='Number of parts for create component in a bar'), 
        'pipe_total': fields.integer('Total pipes', 
            help='Total pipes for create the part')
        }

class ProductPipeMaterial(orm.Model):
    """ Model name: Product
    """    
    _name = 'product.pipe.material'
    _description = 'Pipe description'
    
    _columns = {
        'code': fields.char('Code', size=10),
        'name': fields.char('Pipe material', size=32),
        'first_supplier_id': fields.many2one(
            'res.partner', 'First supplier'),
        'resistence': fields.char('Resistence', size=20),
        'note': fields.text('Note'),
        }

class ProductPipeMaterialLot(orm.Model):
    """ Model name: Product
    """    
    _name = 'product.pipe.material.lot'
    _description = 'Pipe order lot'
    _rec_name = 'material_id'
    
    _columns = {
        'material_id': fields.many2one(
            'product.pipe.material', 'Material'),
        'diameter': fields.float('Diameter mm.', digits=(16, 2)),
        'order_lot': fields.integer('Min. lot', required=True),
        }
    
    _defaults = {
        'order_lot': lambda *x: 1,
        }    

class ProductPipeMaterial(orm.Model):
    """ Model name: Product
    """    
    _inherit = 'product.pipe.material'
    
    _columns = {
        'lot_ids': fields.one2many(
            'product.pipe.material.lot', 'material_id', 
            'Order lot'),
        }

class ProductProduct(orm.Model):
    """ Model name: Product
    """    
    _inherit = 'product.product'
    
    _columns = {
        'is_pipe': fields.boolean('Is Pipe'),
        'pipe_diameter': fields.float('Pipe diameter mm.', digits=(16, 2)),
        'pipe_thick': fields.float('Pipe thick mm.', digits=(16, 2)),
        'pipe_length': fields.float('Pipe length mm.', digits=(16, 2)),
        'pipe_resistence': fields.char('Pipe resistence', size=32),
        'pipe_min_order': fields.integer('Pipe min order'),
        # TODO remove:
        'pipe_material': fields.selection([
            ('fe', 'Iron'),
            ('al', 'Aluminium'),
            ], 'Pipe material'),
        # Override pipe_material:
        'pipe_material_id': fields.many2one(
            'product.pipe.material', 'Material'),     
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
