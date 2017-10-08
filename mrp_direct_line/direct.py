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
import copy
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
        
    def working_mpr_is_ready(self, cr, uid, ids, context=None):
        ''' Set as done this line for the job
        '''
        current_proxy = self.browse(cr, uid, ids, context=context)[0]
        return self.write(cr, uid, ids, {
            'working_ready': True,
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
        'working_done': fields.boolean('Done'), #TODO remove > test working_qty
        'working_ready': fields.boolean('Ready for input', 
            help='Line component are ready in line position'),
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

class MrpProductionStatsMaterial(orm.Model):
    """ Model name: MrpProductionStatsPallet
    """
    
    _name = 'mrp.production.stats.material'
    _description = 'Produce material'
    _rec_name = 'product_id'
    
    _columns = {
        'stats_id': fields.many2one('mrp.production.stats', 'Stats'),
        'sol_id': fields.many2one('sale.order.line', 'Order line'),
        'product_id': fields.many2one('product.product', 'Material'),
        'product_qty': fields.float('Q.ty', digits=(16, 3)),
        'ready_qty': fields.float('Ready', digits=(16, 3)),
        'bom_qty': fields.float('BOM Qty', digits=(16, 3), 
            help='Q.ty for make 1 product (used for check total prod.'),
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
        'pallet_id': fields.many2one('mrp.production.stats.pallet', 'Pallet',
            ondelete='cascade'),
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
        # TODO other related?
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
    
    _php_button_bar = '''
        <a href="/default.php">
            <image src="/images/home.jpg" height="32px" /></a>
        &nbsp;
        <a href="#" onclick="history.back()">
            <image src="/images/back.jpg" height="32px" /></a>
        '''

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
    # XMLRPC Function PHP calls:
    # -------------------------------------------------------------------------
    def set_sol_done_xmlrpc(self, cr, uid, sol_id, mode='line', context=None):
        ''' Mark as confirmed:
        '''        
        if mode == 'line':
            return self.pool.get('sale.order.line').working_qty_is_done(
                cr, uid, [sol_id], context=context)
        else: # 'pre'
            return self.pool.get('sale.order.line').working_mpr_is_ready(
                cr, uid, [sol_id], context=context)
    
    def get_xmlrpc_lines_html(self, cr, uid, context=None):
        ''' Page default.php for all line
        '''
        line_pool = self.pool.get('mrp.workcenter')
        line_ids = line_pool.search(cr, uid, [], context=context)        

        if context is None: 
            context = {}

        total_col = 3
        res = '''
            <table class="topics">
                <tr><th colspan="%s">Linee di produzione [%s]</tr>   
                <tr>''' % (
                    total_col,
                    datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
                    )
        col = 0
        for line in line_pool.browse(cr, uid, line_ids, context=context):
            col += 1
            if col == total_col + 1:
                col = 0
                res += '</tr><tr class="topics">'

            res += '''
                <td class="topics">
                    <a href="./linea.php?linea=%s&mode=pre">
                        <image src="./images/pre.jpg" title="%s" /></a>
                    &nbsp;    
                    <a href="./linea.php?linea=%s">
                        <image src="./images/linea.jpg" title="%s" /></a>
                    <br />
                    %s [%s]
                </td>''' % (
                    # Pre
                    line.code,
                    _('Preparazione linea: %s') % line.name,
                    # Line
                    line.code,
                    _('Linea di produzione: %s') % line.name,
                    # Comment:
                    line.name,
                    line.code,
                    )
                        
        if col == total_col:
            res += '</tr>'
        res += '</table>'        
        return res
        
    def get_xmlrpc_bom_html(self, cr, uid, product_id, context=None):
        ''' PHP call for get BOM
            context parameters:
                > 'noheader': hide header
                > 'show_ready': show only show ready category
                > 'expand': expand halfwork
                > 'qty': calculate total for qty producey
        '''   
        # Read parameters:
        if context is None:
            context = {}

        noheader = context.get('noheader', False)
        show_ready = context.get('show_ready', False)
        expand = context.get('expand', True)
        qty = context.get('qty', 1.0)

        bom = ''
        product_pool = self.pool.get('product.product')
        product_proxy = product_pool.browse(
            cr, uid, product_id, context=context)
        
        # ---------------------------------------------------------------------
        # BOM Lines:
        # ---------------------------------------------------------------------
        for item in sorted(product_proxy.dynamic_bom_line_ids, 
                key=lambda x: (
                    not(x.product_id.half_bom_id), 
                    x.product_id.default_code,
                    )):
            category = item.category_id
            product = item.product_id
            
            if show_ready and not category.show_ready:
                continue # jump category not in show ready status                
            
            # if item.relative_type == 'half'\
            if product.bom_placeholder:
                tag_class = 'placeholder'                
            elif product.half_bom_id:
                tag_class = 'halfworked' 
            else:
                tag_class = 'component'
            
            bom += '''
                <tr class="%s">
                    <td colspan="2">%s</td>
                    <td>%s</td>
                    <td>%s</td>
                    <td>%s %s</td>
                </tr>
                ''' % (
                    tag_class,
                    product.default_code,
                    product.name,
                    item.category_id.name,
                    int(item.product_qty * qty),
                    item.product_uom.name.lower(),
                    )                    
                    
            # Add sub elements (for halfworked)
            if expand: 
                for cmpt in product.half_bom_id.bom_line_ids:                
                    bom += '''
                    <tr class="material">
                        <td>>>></td>
                        <td>%s</td>
                        <td>%s</td>
                        <td>&nbsp;</td>
                        <td>%s %s</td>
                    </tr>
                    ''' % (
                        cmpt.product_id.default_code,
                        cmpt.product_id.name,
                        cmpt.product_qty,
                        cmpt.product_uom.name.lower(),
                        )                   
                                            
        # ---------------------------------------------------------------------
        # Add header:    
        # ---------------------------------------------------------------------
        if noheader:
            header_title = '''
                <tr>
                    <th colspan="9">Componenti da approntare:</th>
                </tr>
                '''
        else:     
            header_title = '''
                <tr>
                    <th colspan="2">%s</th>
                    <th colspan="3">%s [%s]</th>
                </tr>
                ''' % (
                    self._php_button_bar,
                    product_proxy.default_code,
                    product_proxy.name,
                    )
            
        res = _('''
            <tr colspan="9">
            <table class="bom">
                %s
                <tr>
                    <th colspan="2">Codice</th>
                    <th>Descrizione</th>
                    <th>Categoria</th>
                    <th>Q.</th>
                </tr>
                %s
            </table>            
            </tr>
            ''') % (
                header_title,
                bom,
                )
        return res
        
    def get_xmlrpc_html(self, cr, uid, line_code, redirect_url, mode='line',
            context=None):
        ''' Return HTML view for result php call
        '''
        # ---------------------------------------------------------------------
        # UTILITY:
        # ---------------------------------------------------------------------
        # TODO move in note system:
        def get_notesystem_for_line(self, cr, uid, line, context=None):
            ''' Note system for line
            '''
            def add_domain_note(self, cr, uid, line, block='pr', context=None):
                ''' Add domain note after seahch
                '''
                label_image = '''
                    <img src="/images/label.jpg" 
                    alt="Etichetta personalizzata" 
                    style="width:16px;height:16px;"
                    title="Etichetta personalizzata"/> 
                    ''' 
                    
                # Pool used:
                product_pool = self.pool.get('product.product')    
                note_pool = self.pool.get('note.note')

                domain = product_pool.get_domain_note_event_filter(
                    cr, uid, line, block=block, context=context)                
                if domain == False: # no domain
                    return ''
                note_ids = note_pool.search(
                    cr, uid, domain, context=context)

                note_text = ''    
                for note in note_pool.browse(
                        cr, uid, note_ids, context=context):    
                    note_text += '<div class="p_note %s">%s<b>%s</b> %s</div>' % (
                        '"fg_red"' if note.print_label else '',
                        label_image if note.print_label else '',
                        note.name or '', 
                        note.description or '',
                        )
                return note_text        
            
            note_text = ''
            # TODO add only category for production in filter!
            
            # Product note:
            mask = '<b class="category_note">NOTE %s: </b><br/>%s'
            res = add_domain_note(
                self, cr, uid, line, block='pr', context=context)            
            if res:
                note_text += mask % ('PRODOTTO', res)
            # Partner note:
            res = add_domain_note(
                self, cr, uid, line, block='pa', context=context)            
            if res:
                note_text += mask % ('PARTNER', res)
            # Address note:
            res = add_domain_note(
                self, cr, uid, line, block='ad', context=context)
            if res:
                note_text += mask % ('INDIRIZZO', res)
            # Order note:
            res = add_domain_note(
                self, cr, uid, line, block='or', context=context)
            if res:
                note_text += mask % ('ORDINE', res)
            # Detail note:
            res = add_domain_note(
                self, cr, uid, line, block='pr-de', context=context)
            if res:
                note_text += mask % ('DETTAGLIO', res)

            # Partner product note:
            res = add_domain_note(
                self, cr, uid, line, block='pr-pa', context=context)
            if res:
                note_text += mask % ('PRODOTTO-CLIENTE', res)
            # Address product note:
            res = add_domain_note(
                self, cr, uid, line, block='pr-ad', context=context)
            if res:
                note_text += mask % ('PRODOTTO-INDIRIZZO', res)
            # Address product order note:
            res = add_domain_note(
                self, cr, uid, line, block='pr-or', context=context)
            if res:
                note_text += mask % ('PRODOTTO-ORDINE', res)
            
            return note_text
        
        # Pool used:
        product_pool = self.pool.get('product.product')
        note_pool = self.pool.get('note.note')
        line_pool = self.pool.get('mrp.workcenter')

        if context is None: 
            context = {}
        
        now = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        album_ctx = context['album_code'] = 'CHROMA'

        # Line information:
        line_ids = line_pool.search(cr, uid, [
            ('code', '=', line_code),
            ], context=context)
        if not line_ids:
            return _('<p>Line not present</p>')
            
        stats_ids = self.search(cr, uid, [
            ('working_done', '=', False),
            ('workcenter_id', '=', line_ids[0]),
            ('date', '=', now[:10]),
            ], context=context)
        if not stats_ids:
            return _('<p>Nothing to work in line %s today!</p>') % line_code
        
        # ---------------------------------------------------------------------
        # Header:
        # ---------------------------------------------------------------------
        res = ''
        max_queue = 3
        for stats in self.browse(cr, uid, stats_ids, context=context)[0]: # XXX only first?
            res = '''
                <table>
                    <tr>
                        <th colspan="1">
                            %s
                        </th>
                        <th colspan="4">%s</th>
                        <th colspan="4">Aggiornato il: %s</th>
                    </tr>
                ''' % (
                    self._php_button_bar,
                    stats.workcenter_id.name,        
                    now,
                    )

            first = False
            second = 0
            
            # Context for pre mode: XXX only for pre check? 
            ctx = copy.deepcopy(context)
            ctx['noheader'] = True
            ctx['show_ready'] = True
            ctx['expand'] = False
            for line in sorted(stats.working_ids, 
                    key=lambda x: (x.working_sequence, x.mrp_sequence)):
                
                # -------------------------------------------------------------                    
                # Jump record not used:
                # -------------------------------------------------------------                    
                if mode == 'line' and not line.working_qty:
                    continue # line and production done
                if mode == 'pre' and line.working_ready: 
                    continue # pre line and yet prepared

                product = line.product_id
                q_x_pack = int(product.q_x_pack) # item_per_box
                item_per_pallet = int(product.item_per_pallet)
                
                ctx['qty'] = line.working_qty # only working           
                
                #if line.product_uom_qty <= line.product_uom_maked_sync_qty:
                #    continue
                if not first:
                    first = True

                    # ---------------------------------------------------------
                    #                  INFORMATION NOTE:
                    # ---------------------------------------------------------
                    note_text = get_notesystem_for_line(
                        self, cr, uid, line, context=context)
                    
                    # ---------------------------------------------------------
                    # Print part:
                    # ---------------------------------------------------------
                    res += _('''
                        <tr>
                            <td colspan="1">
                                <a href="./php/bom.php?product_id=%s">
                                <image src="./images/distinta.jpg" 
                                    alt="Distinta base" />
                                </a>    
                            </td>
                            <td colspan="4">
                                <b>Produzione: %s [%s]</b>
                            </td>
                            <td colspan="4">
                                <form action="/php/print.php" method="get">
                                    <input type="submit" value="Tutte" 
                                        class="print_button" name="all"
                                        title="Stampa tutte le etichette del job attuale (giornata)"
                                        />
                                    &nbsp;
                                    <input type="submit" value="Interna" 
                                        class="print_button" name="internal"
                                        title="Stampa le etichette interne del job attuale (giornata)"
                                        />
                                    &nbsp;
                                    <input type="submit" value="Esterna" 
                                        class="print_button" name="external"
                                        title="Stampa le etichette esterne del job attuale (giornata)"
                                        />
                                    &nbsp;
                                    <input type="hidden" name="sol_id" 
                                        value="%s">
                                    <input type="hidden" name="redirect_url" 
                                        value="%s">
                                    <input type="input" name="total" value="" 
                                        maxlength="4" size="4" 
                                        title="Q. per stampare la sola etichetta corrente">
                                </form>
                            </td>
                        </tr>''') % (
                            line.product_id.id,
                            line.mrp_id.name,
                            line.mrp_id.bom_id.name,
                            line.id, redirect_url,
                            )                            
                        
                    # ---------------------------------------------------------
                    # Header block (print button and title)
                    # ---------------------------------------------------------
                    res += _('''                            
                        <tr class="bg_blue">
                            <td>Partner</td><td>Destinazione</td>
                            <td>Ordine</td><td>Codice</td><td>Pezzi</td>
                            <td>Q. x sc.</td><td>Q. x ban.</td>
                            <td>Conferma</td><td>OK</td>
                        </tr>
                        ''')      
                    
                    # ---------------------------------------------------------
                    # Current record:
                    # ---------------------------------------------------------
                    if mode == 'line':
                        button_confirm = 'FATTI!'
                        hidden_mode = '''
                           <input type="hidden" name="mode" value="line">'''
                    else:
                        button_confirm = 'APPRONTATI!'
                        hidden_mode = '''
                           <input type="hidden" name="mode" value="pre">'''

                    res += _('''    
                        <tr>
                            <td>%s</td><td>%s</td><td>%s</td>
                            <td><b>%s</b></td>
                            <td><b>%s</b></td>
                            <td>%s</td><td>%s</td>
                            <td>
                                <form action="/php/confirm.php" method="get">
                                    <input type="submit" value="%s">
                                    <input type="hidden" name="sol_id" 
                                        value="%s">
                                    <input type="hidden" name="redirect_url" 
                                        value="%s">
                                    %s    
                                </form>
                            </td>
                            <td>
                                <image src="./images/%s.gif"
                                    title="%s" />
                            </td>
                        </tr>''') % (
                            line.partner_id.name, 
                            line.order_id.destination_partner_id.name or \
                                '&nbsp;', 
                            line.order_id.name,
                            line.default_code, line.working_qty,
                            q_x_pack, item_per_pallet,
                            
                            # Confirm form:
                            button_confirm,
                            line.id, 
                            redirect_url,
                            hidden_mode,
                            'green' if line.working_ready else 'red',
                            _('Materiale pronto per la produzione') if\
                                line.working_ready else _(
                                    'Materiale non pronto per la produzione'),
                            
                            )
                                                    
                    # ---------------------------------------------------------
                    # Extra info for current record:
                    # ---------------------------------------------------------
                    if mode == 'line':
                        res += _('''
                            <tr>
                                <td>
                                    <img alt="Immagine non trovata" 
                                        src="data:image/png;base64,%s" />
                                </td>
                                <td colspan="8" class="text_note">
                                    %s<p>%s</p>
                                </td>
                            </tr>
                            </table>''') % (
                                line.product_id.product_image_context,
                                _('<p class="fg_red">ETICHETTA PERSONALIZZATA</p>'
                                    ) if line.partner_id.has_custom_label else \
                                        _('<p>ETICHETTA MAGAZZINO</p>'),                              
                                note_text,
                                )
                    else: # 'pre'
                        res += _('''
                            <tr>
                                <td colspan="7" class="text_note">
                                    <p>%s</p>
                                </td>
                            </tr>
                            </table>''') % (
                                self.get_xmlrpc_bom_html(
                                    cr, uid, product.id, context=ctx),
                                )
                                
                    #line.order_id.company_id.logo or ''
                        
                    # ---------------------------------------------------------
                    # Next element from here:
                    # ---------------------------------------------------------
                    res += _('''<table class="table_preview">''') 

                    res += _('''
                        <tr>
                            <td colspan="9"><b>PROSSIME:</b></td>
                        </tr>
                        <tr class="bg_blue">
                           <td>Partner</td><td>Destinazione</td><td>Ordine</td>
                           <td>Codice</td><td>Pezzi</td>
                           <td>Q. x sc.</td><td>Q. x ban.</td>
                           <td>OK</td>
                       </tr>
                        ''')
                        
                else: # second
                    second += 1
                    if second > max_queue:
                        break
                    res += '''
                        <tr>
                            <td>%s</td><td>%s</td><td>%s</td>
                            <td><b>%s</b></td>
                            <td><b>%s</b></td>
                            <td>%s</td><td>%s</td>
                            <td>
                                <image src="./images/%s.gif" title="%s" />
                            </td>
                        </tr>''' % (
                            line.partner_id.name,
                            line.order_id.destination_partner_id.name or \
                                '&nbsp;',
                            line.order_id.name,
                            line.default_code,
                            line.working_qty,                 
                            q_x_pack, 
                            item_per_pallet,
                            'green' if line.working_ready else 'red',
                            _('Materiale pronto per la produzione') if\
                                line.working_ready else _(
                                    'Materiale non pronto per la produzione'),
                            )
        res += '</table>'                
        return res
        
    # -------------------------------------------------------------------------
    # Button event:    
    # -------------------------------------------------------------------------   
    def generate_material_planned_bom(self, cr, uid, ids, context=None):
        ''' Generate material list for working product in lavoration
        '''
        material_pool = self.pool.get('mrp.production.stats.material')
        
        stats_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        # Delete material before:
        material_ids = [m.id for m in stats_proxy.material_ids]
        material_pool.inlink(cr, uid, material_ids, context=context)
        
        for line in stats_proxy.working_ids:
            for material in line.product_id.dynamic_bom_line_ids):
                product = material.product_id            
                if not item.category_id.show_ready:
                    continue # jump category not in show ready status
                
                material_pool.create(cr, uid, {  
                    'stats_id': ids[0],
                    'sol_id': line.id,
                    'product_id': product.id,
                    'product_qty': material.product_qty * line.working_qty,
                    'bom_qty': material.product_qty,
                    'ready_qty': 0.0,                                       
                    }, context=context)
        return True        
 
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
            hour = (duration.seconds / 3600.0 )  + (duration.days * 24.0)
        else:        
            hour = 0.0

        # Auto total count:
        working_end_total = self.get_current_production_number(
            cr, uid, ids, context=context)        
        total = working_end_total - current_proxy.working_start_total
        if total <= 0:
            total = 0
            
        return self.write(cr, uid, ids, {
            'total': total,
            'crono_stop': crono_stop.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
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
        css = '''
            <style>
                .table_bf {
                     border:1px 
                     padding: 3px;
                     solid black;
                 }
                .table_bf td {
                     border:1px 
                     solid black;
                     padding: 3px;
                     text-align: center;
                 }
                .table_bf th {
                     border:1px 
                     solid black;
                     padding: 3px;
                     text-align: center;
                     background-color: grey;
                     color: white;
                 }
            </style>
            '''
        max_second = 3
        res = {}

        for stats in self.browse(cr, uid, ids, context=context):
            res[stats.id] = {}            
            res[stats.id]['working_line_current'] = ''
            res[stats.id]['working_line_next'] = '''
                  %s
                  <table class='table_bf'>
                        <tr>
                            <td>Partner</td>
                            <td>Order</td>
                            <td>Code</td>
                            <td>Work q.</td>
                        </tr>
                  ''' % css

            first = False
            second = 0
            for line in sorted(stats.working_ids, 
                    key=lambda x: (x.working_sequence, x.mrp_sequence)):
                # Check if is done:
                if not line.working_qty:
                    continue
                #if line.product_uom_qty <= line.product_uom_maked_sync_qty:
                #    continue
                if not first:
                    first = True
                    res[stats.id]['working_line_current'] = '''
                        %s
                        <p>
                            <b>%s</b>
                        </p>
                        <table class='table_bf'>
                            <tr>
                                <td>Partner</td><td>Order</td>
                                <td>Code</td><td>Work q.</td>
                            </tr>
                            <tr>
                                <td>%s</td><td>%s</td>
                                <td>%s</td><td>%s</td>
                            </tr>                       
                        </table>
                        ''' % (
                            css,
                            _('ETICHETTA PERSONALIZZATA!!!') if \
                                line.partner_id.has_custom_label else \
                                    _('ETICHETTA MAGAZZINO'),
                            line.partner_id.name,
                            line.order_id.name,
                            line.default_code,
                            line.working_qty,
                            )
                else: # second
                    second += 1
                    if second > max_second:
                        break
                    res[stats.id]['working_line_next'] += '''
                        <tr>
                            <td>%s</td><td>%s</td><td>%s</td><td>%s</td>
                        </tr>''' % (
                            line.partner_id.name,
                            line.order_id.name,
                            line.default_code,
                            line.working_qty,                                
                            )

            res[stats.id]['working_line_next'] += '</table>'
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
            
        'material_ids': fields.one2many(
            'mrp.production.stats.material', 'stats_id', 'Material'),
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
    
class MrpBomStructureCategory(orm.Model):
    """ Model name: Manage structure for show bom
    """
    
    _inherit = 'mrp.bom.structure.category'
    
    _columns = {
        'show_ready':fields.boolean('Show ready',
            help='Show in PHP view for MRP status'),
        }

class SaleOrderLine(orm.Model):
    ''' Link line for stats
    '''
    _inherit = 'sale.order.line'

    def _get_check_material_ready(self, cr, uid, ids, fields, args, 
            context=None):
        ''' Fields function for calculate 
        '''
        res = {}
        for sol in self.browse(cr, uid, ids, context=context):
            res[sol.id] = {}
            res[sol.id]['material_ready'] = True
            res[sol.id]['material_max'] = sol.working_qty # this prod. to work
            
            for material in sol.material_ids:
                ready_qty = material.ready_qty
                product_qty = material.product_qty
                if ready_qty < product_qty: # material not all present
                    # If one component non present ready is false:
                    res[sol.id]['material_ready'] = False
                    material_max = ready_qty / bom_qty # TODO round(, 0)?
                    
                    # Max verification:
                    if material_max < res[sol.id]['material_max']:
                        res[sol.id]['material_max'] = material_max
        return res    

    _columns = {
        # Not in views only for calculated field:
        'material_ids': fields.one2many(
            'mrp.production.stats.material', 'sol_id', 'Materials'),
        'material_max': fields.function(
            _get_check_material_ready, method=True, multi=True,
            type='float', string='Max production', store=False),
        'material_ready': fields.function(
            _get_check_material_ready, method=True, multi=True,
            type='boolean', string='Ready', store=False),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
