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
import math
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
    
    def realculate_all_price(self, cr, uid, ids, context=None):
        ''' Manually launch schedule operation
        '''
        self.pool.get('product.product').schedule_pipe_price_calculation(
            cr, uid, context=context)
            
    _columns = {
        'code': fields.char('Code', size=10),
        'name': fields.char('Pipe material', size=32),
        'first_supplier_id': fields.many2one(
            'res.partner', 'First supplier'),
        'resistence': fields.char('Resistence', size=20),
        'note': fields.text('Note'),
        'weight_specific': fields.float(
            'Weight specific (Kg/dm3)', digits=(16, 10)),
        'last_price': fields.float('Last price', digits=(16, 4)),
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
    
    # Scheduled operations:
    def schedule_pipe_price_calculation(self, cr, uid, context=None):
        ''' Calculate all pipe value if weight / volume is present
        '''
        pipe_ids = self.search(cr, uid, [
            ('is_pipe', '=', True),
            ('pipe_material_id.weight_specific', '>', 0.0), # has wh/vol.
            ('pipe_material_id.last_price', '>', 0.0), # has price
            ], context=context)
        return self.calculate_pipe_price_from_dimension(
            cr, uid, pipe_ids, context=context)
            
    def calculate_pipe_price_from_dimension(self, cr, uid, ids, context=None):
        ''' Calculate volume depend on dimension of pipe and weight / volume
            remove auto weight, use context parameter
        '''
        # Auto weight parameter:
        if context is None:
            context = {}
        auto_weight = context.get('auto_weight', False)
            
        # Used from button but also for scheduled operation
        for product in self.browse(cr, uid, ids, context=context):            
            data = {}            
            if auto_weight:
                _logger.warning('Auto calculation weight mode')
                thick = product.pipe_thick
                
                # Area:
                ray1 = product.pipe_diameter / 2
                if product.pipe_diameter2:
                    ray2 = product.pipe_diameter2 / 2
                else:    
                    ray2 = ray1
                    
                plain_area = ray1 * ray2 * math.pi
                empty_area = (ray1 - thick) * (ray2 - thick) * math.pi
                
                # Volume:    
                plain_volume = plain_area * product.pipe_length
                empty_volume = empty_area * product.pipe_length
                volume = (plain_volume - empty_volume) / 1000000 # m3
                
                # Weight:
                weight = volume * product.pipe_material_id.weight_specific
                data['weight'] = weight
            else:
                _logger.warning('No auto calculation weight mode')
                weight = product.weight    

            # Price: 
            data['standard_price'] = \
                weight * product.pipe_material_id.last_price
            self.write(cr, uid, product.id, data, context=context)
        
    _columns = {
        'is_pipe': fields.boolean('Is Pipe'),
        'pipe_diameter': fields.float('Pipe diameter mm.', digits=(16, 2)),
        'pipe_diameter2': fields.float('Pipe diameter 2 mm.', 
            digits=(16, 2), help='For elliptic pipes'),
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
