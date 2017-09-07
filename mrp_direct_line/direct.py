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
import StringIO
import base64
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
    def working_qty_is_done(self, cr, uid, ids, context=None):
        ''' Set as done this line for the job
        '''
        current_proxy = self.browse(cr, uid, ids, context=context)[0]
        return self.write(cr, uid, ids, {
            'working_qty': 0,
            'product_uom_maked_sync_qty': 
                current_proxy.product_uom_maked_sync_qty + \
                current_proxy.working_qty,
            }, context=context)
        
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
        'id': fields.integer('QRcode ID'),
        'create_date': fields.datetime('Create date'),
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
        'default_code': fields.related('sol_id', 'default_code',
            type='char', string='Default code'),
        'partner_id': fields.related(
            'sol_id', 'partner_id', 
            type='many2one', relation='res.partner', string='Partner'),    
        'order_id': fields.related(
            'sol_id', 'order_id', 
            type='many2one', relation='sale.order', string='Order'),
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
    # Utility:
    # -------------------------------------------------------------------------
    def get_current_production_number(self, cr, uid, ids, context=None):
        ''' Calculate current production data sync
        '''
        total = 0
        for line in self.browse(cr, uid, ids, context=context)[0].working_ids:
            total += line.product_uom_maked_sync_qty            
        return total

    # -------------------------------------------------------------------------
    # Button event:    
    # -------------------------------------------------------------------------    
    def working_new_pallet(self, cr, uid, ids, context=None):
        ''' New pallet
        '''
        working_pallet = {}
        for line in self.browse(cr, uid, ids, context=context)[0].working_ids:
            if line.product_uom_maked_sync_qty:
                working_pallet[line.id] = line.product_uom_maked_sync_qty
        self.write(cr, uid, ids, {
            'working_pallet': '%s' % (working_pallet, )
            }, context=context)
        return True
        
    def working_end_pallet(self, cr, uid, ids, context=None):
        ''' End pallet
        ''' 
        pallet_pool = self.pool.get('mrp.production.stats.pallet')
        row_pool = self.pool.get('mrp.production.stats.pallet.row')
        
        job_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        previous_pallet = eval(job_proxy.working_pallet) or {}
        sequence = 1 # TODO get last!
        pallet_id = pallet_pool.create(cr, uid, {
            'sequence': sequence, 
            #'create_date':,             
            'stats_id': ids[0],
            }, context=context)
        sequence = 0    
        for line in job_proxy.working_ids:
            previous = previous_pallet.get(line.id, 0)
            current = line.product_uom_maked_sync_qty
            pallet_qty = current - previous
            if pallet_qty > 0:
                sequence += 1
                row_pool.create(cr, uid, {
                    'sequence': sequence,
                    'quantity': pallet_qty,
                    'pallet_id': pallet_id,
                    'sol_id': line.id,
                    }, context=context)
        self.write(cr, uid, ids, {
            'working_pallet': False,
            }, context=context)            
        return True
    
    # Start / Stop management:
    def working_crono_start(self, cr, uid, ids, context=None):
        ''' Start event:
        '''
        return self.write(cr, uid, ids, {
            'crono_start': datetime.now().strftime(
                DEFAULT_SERVER_DATETIME_FORMAT),
            }, context=context)
        
    def working_mark_as_done(self, cr, uid, ids, context=None):
        ''' Print single label
        '''
        current_proxy = self.browse(cr, uid, ids, context=context)[0]
        crono_stop = datetime.now()
        if current_proxy.crono_start:
            duration = crono_stop - datetime.strptime(
                current_proxy.crono_start,
                DEFAULT_SERVER_DATETIME_FORMAT,
                )
            import pdb; pdb.set_trace()    
            hour = duration.hours + (duration.seconds / 60.0) + (
                duration.days * 24.0)
        else:        
            hour = 0.0

        # Auto total count:
        working_end_total = stats_pool.get_current_production_number(
            cr, uid, ids, context=context)        
        total = working_end_total - current_proxy.working_start_total    
        if total <= 0:
            total = 0
            
        return self.write(cr, uid, ids, {
            'total': total,
            'crono_stop': crono_stop,
            'hour': hour,
            'working_done': True,
            }, context=context)

    def working_print_all_label(self, cr, uid, ids, context=None):
        ''' Print single label
        '''    
        return True

    def nothing(self, cr, uid, ids, context=None):
        ''' Do nothing
        '''
        return True     

    # Fields function:
    def _get_working_line_status(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate 
        '''
        res = {}
        for stats in self.browse(cr, uid, ids, context=context):
            res[stats.id] = {}
            res[stats.id]['working_line_current'] = ''
            res[stats.id]['working_line_next'] = ''            
        return res
        
    _columns = {
        # If use crono automatic:
        'crono_start': fields.datetime(
            'Start time', 
            help='Start time for automated hour calc when close the day',
            ),
        'crono_stop': fields.datetime('Stop time'),
        'working_start_total': fields.integer('Start total ', 
            help='Used for get total at the end of the day'),
        
        # Line data:
        'working_line_current': fields.function(
            _get_working_line_status, method=True, 
            type='text', string='Current', 
            store=False, multi=True), 
        'working_line_next': fields.function(
            _get_working_line_status, method=True, 
            type='text', string='Next', 
            store=False, multi=True), 
        
        'pallet_ids': fields.one2many(
            'mrp.production.stats.pallet', 'stats_id', 'Pallet'),
        'working_ids': fields.one2many(
            'sale.order.line', 'working_line_id', 'Working line',
            help='Sale order line working on this day'),
        'working_done': fields.boolean('Done'),
        'working_pallet': fields.text(
            'Working pallet situation', 
            help='Not visible: store the data for new pallet situation'),
        }
    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
