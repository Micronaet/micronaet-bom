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
import qrcode
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

class MrpProductionStatsPallet(orm.Model):
    """ Model name: MrpProductionStatsPallet
    """
    
    _name = 'mrp.production.stats.pallet'
    _description = 'Pallet produced'
    _rec_name = 'sequence'
    _order = 'sequence,id'
    
    def _create_qr_code_package(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate 
        '''
        import StringIO
        import base64
        
        res = {}
        for pallet in self.browse(cr, uid, ids, context=context):
            res[pallet.id] = {}
            qrcode_text = _(
                'ID: %s [%s in MRP: %s]\nFamily %s\nDate: %s') % (
                    pallet.id, 
                    pallet.sequence,
                    pallet.stats_id.mrp_id.name,
                    pallet.stats_id.mrp_id.product_id.name, # Family
                    pallet.create_date,
                    )
            res[pallet.id]['qrcode'] = qrcode_text
            #import pdb; pdb.set_trace()
            img = qrcode.make(qrcode_text)
            s = StringIO.StringIO()
            img.save(s)#, 'jpg')
            img_bin = base64.b64encode(s.getvalue())

            res[pallet.id]['qrcode_image'] = img_bin
                    
        return res
    
    _columns = {
        'create_date': fields.date('Create date'),
        'sequence': fields.integer('Seq.'),
        'stats_id': fields.many2one('mrp.production.stats', 'Stats'),
        'ean13': fields.char('EAN 13', size=13),
        'qrcode': fields.function(
            _create_qr_code_package, method=True, 
            type='char', size=100, string='QR Code', store=False, 
            readonly=True, multi=True,
            ), 
        'qrcode_image': fields.function(
            _create_qr_code_package, string='QR Code image',method=True, 
            type='binary', store=False, readonly=True, multi=True
            ),
        # TODO total pieces
        }

class MrpProductionStatsPalletRow(orm.Model):
    """ Model name: MrpProductionStatsPallet
    """
    
    _name = 'mrp.production.stats.pallet.row'
    _description = 'Pallet row produced'
    _rec_name = 'sol_id'
    _order = 'sequence,id'
    
    _columns = {
        'sequence': fields.integer('Seq.'),
        'pallet_id': fields.many2one('mrp.production.stats.pallet', 'Pallet'),
        'sol_id': fields.many2one('sale.order.line', 'Line'),
        'quantity': fields.integer('Q.', required=True),
        # TODO related (partner, destination, code)
        }

class MrpProductionStatsPallet(orm.Model):
    """ Model name: MrpProductionStatsPallet
    """
    
    _inherit = 'mrp.production.stats.pallet'
    
    _columns = {
        'content_ids': fields.one2many(
            'mrp.production.stats.pallet.row', 'pallet_id', 'Content'),
        }

class MrpProductionStat(orm.Model):
    ''' Statistic data
    '''
    _inherit = 'mrp.production.stats'

    # -------------------------------------------------------------------------
    # Button event:    
    # -------------------------------------------------------------------------    
    def working_new_pallet(self, cr, uid, ids, context=None):
        ''' New pallet
        '''    
        return True
        
    def working_end_pallet(self, cr, uid, ids, context=None):
        ''' End pallet
        '''    
        return True
    
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
        'pallet_ids': fields.one2many(
            'mrp.production.stats.pallet', 'stats_id', 'Pallet'),
        'working_ids': fields.one2many(
            'sale.order.line', 'working_line_id', 'Working line',
            help='Sale order line working on this day'),
        'working_done': fields.boolean('Done'),            
        }
    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
