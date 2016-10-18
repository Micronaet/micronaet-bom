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

class MRPBom(orm.Model):
    """ Model name: MRPBom
    """    
    _inherit = 'mrp.bom'

    # EXTRA BLOCK -------------------------------------------------------------
    def migrate_assign_parent_bom(self, cr, uid, ids, context=None):
        ''' Migrate bom in dynamic way
        '''
        assert len(ids) == 1, 'Works only with one record a time'

        line_pool = self.pool.get('mrp.bom.line')
        
        # Create rule in dynamic:
        bom_proxy = self.browse(cr, uid, ids, context=context)[0]
        structure = bom_proxy.product_id.structure_id
        
        for line in bom_proxy.bom_line_ids:
            line_pool.create(cr, uid, {
                'bom_id': structure.dynamic_bom_id.id,
                'product_id': line.product_id.id,
                'dynamic_mask': '%s%s' % (bom_proxy.product_id.code, '%'),
                'product_qty': line.product_qty,
                'product_uom': line.product_uom.id,                                
                }, context=context)
        
        # Move in to be remove category
        self.write(cr, uid, ids, {
            'bom_category': 'remove',
            }, context=context)
        return True

    def migrate_assign_product_bom_product(self, cr, uid, ids, context=None):
        ''' Loop button:
        '''
        product_pool = self.pool.get('product.product')
        
        product_ids = self.search(cr, uid, [
            ('bom_category', '=', 'product')], context=context)

        # LOG operation (TODO remove)
        log_f = open(os.path.expanduser('~/bom.csv'), 'w')

        dimension_db = {}        
        for item in product_ids: #XXX ids:
            message = self.migrate_assign_product_bom_product1(
                cr, uid, [item], dimension_db, context=context)
            log_f.write(message)    
        log_f.close()        
        return True    
        
    def migrate_assign_product_bom_product1(self, cr, uid, ids, dimension_db, 
            context=None):
        ''' Migrate bom in dynamic way
            Create half work element
            Create BOM 
            Create move in dynamic
        '''
        assert len(ids) == 1, 'Works only with one record a time'

        # Pool used
        line_pool = self.pool.get('mrp.bom.line')
        product_pool = self.pool.get('product.product')
        bom_proxy = self.browse(cr, uid, ids, context=context)[0]

        log = ''
        
        try:
            dynamic_bom_id = \
                bom_proxy.product_id.structure_id.dynamic_bom_id.id
            structure_id = bom_proxy.product_id.structure_id.id
        except:
            # no dynamic BOM
            log += '???|||%s|No dynamic bom structure\n' % ( 
                bom_proxy.name,
                )
            return log
                    
        # ---------------------------------------------------------------------
        # Create dynamic mask from code:
        # ---------------------------------------------------------------------
        code_map = {
            #Parent:Tela
            '029': '129',
            '030': '130',
            '027': '127',
            '026': '127',
            '126': '127',
            '028': '128',
            '045': '145',
            '048': '145',
            '148': '145',
            '049': '145',
            '149': '145',
            '121': '021',
            '023': '123',
            '124': '024',
            '014': '024',
            '005': '205',
            '035': '135',
            '036': '135',
            '136': '135',
            '034': '135', # parasole
            '039': '135', # parasole
            '051': '050', # parasole e poggiatesta
            '071': '070', # parasole
            '170': '070',
            '171': '070', # parasole
            '031': '131',
            '032': '132',
            '552': '550',
            '905': '900',
            '935': '930',
            '936': '931',
            '235': '230',
            }
            
        type_map = {
            'TES': 'TL',
            'TEX': 'TL',
            
            # Non usati:
            'TXM': 'TL',
            'TWH': 'TL',
            'TXR': 'TL',
            'TJO': 'TL',
            'TIO': 'TL',
            'TWL': 'TL',
            'TGT': 'TL',           
            
            'TSK': 'MT',
            'T3D': 'MT',
            }
             
        code6_map = {
            # TODO 
            #'TL127S': 'TL127PO'
            }
            
        if not bom_proxy.product_id:
            pr_ids = product_pool.search(cr, uid, [
                ('product_tmpl_id', '=', bom_proxy.product_tmpl_id.id),
                ], context=context)
            if pr_ids:
                default_code = product_pool.browse(
                    cr, uid, pr_ids, context=context)[0]
        default_code = bom_proxy.product_id.default_code
        
        if not default_code:
            log += '???|%s||%s|No codice x BOM\n' % ( 
                len(bom_proxy.bom_line_ids),
                bom_proxy.name,
                )
            return log
            
        default_code = default_code.upper()
        
        # Set mask for unique element S and no S are the same
        if default_code[12:13] == 'S':
            dynamic_mask = default_code[:12] + '%'
        else:
            dynamic_mask = default_code + '%'
        
        log += '%s|%s|%s|%s\n' % (
            default_code, 
            len(bom_proxy.bom_line_ids),
            dynamic_mask, 
            bom_proxy.name or '???', # or bom_proxy.product_tmpl_id.name, 
            )
        
        # TODO Check if dynamic and product are jet present
        
        # ---------------------------------------------------------------------
        # Create TL element:
        # ---------------------------------------------------------------------
        for line in bom_proxy.bom_line_ids:
            component_code = line.product_id.default_code
            if not component_code:
                log += '%s|||%s||No codice componente\n' % (
                    default_code, bom_proxy.name)
                return log
            component_code = component_code.upper()
            
            comment = ''

            # Type code:
            #type_code = 'TL'
            
            # Parent code:
            parent = default_code[:3]
            if parent in ('810', '081', '085'):
                type_code = 'PVC6LU'
                parent_code = ''
            elif parent in ('084', ):
                type_code = 'PVC6OP'
                parent_code = ''
            else: 
                # Default code:    
                parent_code = code_map.get(parent, parent)
                type_code = type_map.get(component_code[:3], False)
                
            
            #Fabric code:
            if parent in ('810', '081', '085', '084'):
                fabric_code = ''
            else:
                # Default code:                
                if 'B' in default_code[4:6]:
                    fabric_code = default_code[3:6].replace('B', ' ')
                else:    
                    fabric_code = default_code[3:6]

            # Color code        
            color_code = default_code[8:12].strip()
            if len(color_code) == 1:
                comment += 'Codice colore 1 carattere'
            
            HW_code = '%s%s%s%s' % (
                type_code or '??',
                parent_code,
                fabric_code, 
                color_code,
                )
            component_ids = product_pool.search(cr, uid, [
                ('default_code', '=', HW_code)], context=context)
            
            # check dimemnsion:
            product_qty = line.product_qty
            if HW_code not in dimension_db:
               dimension_db[HW_code] = product_qty
            
            if product_qty != dimension_db[HW_code]:
                comment += 'Differenze di metratura!!!!'
                
            if not type_code:
                comment += 'Non trovato il tipo MT o TL?'

            if component_ids:
                if len(component_ids) > 1:
                    log += '%s||||%s|%s|%s|Piu componenti|NO|%s\n' % (
                        default_code,
                        component_code, HW_code, product_qty, comment)
                else:
                    log += '%s||||%s|%s|%s||SI||%s\n' % (
                        default_code,
                        component_code, HW_code, product_qty, comment)
            else:        
                log += '%s||||%s|%s|%s|Non trovato in ODOO|%s|NO\n' % (
                    default_code,
                    component_code, HW_code, product_qty, comment)
            
        print log; return log
        """        
            # -----------------------------------------------------------------
            # Create / Update component product and BOM (halfwork)
            # -----------------------------------------------------------------
            HW_ids = product_pool.search(cr, uid, [
                ('default_code', '=', HW_code)], context=context)
             
            if HW_ids: # Update halfcomponent product (and delete line)
                if len(HW_ids) > 1:
                    log += '%s||||%s|%s|%s||SI||%s\n' % (
                        default_code,
                        component_code, HW_code, product_qty, 'more than one')
                        
                HW_id = HW_ids[0]
                product_pool.write(cr, uid, HW_ids, {
                    'halfwork': True,       
                    'half_bom_ids': [(5, False, False)], # XXX remove line
                    }, context=context)                
            else: # Create half component product 
                HW_id = product_pool.create(cr, uid, {
                    'name': HW_code,
                    'default_code': HW_code,
                    'halfwork': True,
                    'structure_id': structure_id,
                    'uom_id': 1, # XXX NR
                    'ean13_auto': False, # XXX
                    }, context=context)

            # -------------------------------------------------------------
            # Create / Update fabric under HW component
            # -------------------------------------------------------------
            # Read record:
            HW_proxy = product_pool.browse(cr, uid, HW_id, context=context)    
            
            # Launch button:
            if not HW_proxy.half_bom_id: 
                product_pool.create_product_half_bom(
                    cr, uid, [HW_id], context=context)

            # Read again product:
            HW_proxy = product_pool.browse(cr, uid, HW_id, context=context)    
            
            line_pool.create(cr, uid, {
                # Link:
                'bom_id': HW_proxy.half_bom_id.id, # bom link
                'halfwork_id': HW_proxy.id, # product link
                
                # Fabric data:
                'product_id': line.product_id.id, 
                'product_uom': line.product_uom.id, 
                'type': line.type,
                'product_qty': line.product_qty,
                }, context=context)

            # -----------------------------------------------------------------
            # Create / Update rule in dynamic:
            # -----------------------------------------------------------------
            line_ids = line_pool.search(cr, uid, [
                ('bom_id', '=', dynamic_bom_id), # dynamic bom for structure
                ('dynamic_mask', '=', dynamic_mask), # mask
                ('product_id', '=', HW_proxy.id), 
                ], context=context)
            if line_ids: # Update or check
                pass
            else: # Create
                line_pool.create(cr, uid, {
                    'bom_id': dynamic_bom_id,
                    'dynamic_mask': dynamic_mask,
                    'product_id': HW_proxy.id, 
                    'product_uom': HW_proxy.uom_id.id, 
                    'product_qty': 1, # always!
                    'type': 'normal',
                    }, context=context)
                            
        print log        
        return log"""

    # EXTRA BLOCK -------------------------------------------------------------
        
    def get_config_parameter_list(self, cr, uid, context=None):
        ''' Read parameter: 
        '''    
        key = 'product.default.product.parent.bom'
        config_pool = self.pool.get('ir.config_parameter')
        config_ids = config_pool.search(cr, uid, [
            ('key', '=', key)], context=context)
        if not config_ids:
            _logger.warning('Parameter not found: %s' % key)
            return []
        config_proxy = config_pool.browse(
            cr, uid, config_ids, context=context)[0]
        return eval(config_proxy.value)    
    
    def assign_parent_bom(self, cr, uid, ids, context=None):
        ''' Assign bom depend on code format
        '''    
        bom_code_split = self.get_config_parameter_list(
            cr, uid, context=context)
        if not bom_code_split:
            raise osv.except_osv(
                _('Error'), 
                _('Setup config paremeter!'))
            
        bom_proxy = self.browse(cr, uid, ids, context=context)[0]
        default_code = bom_proxy.product_id.default_code
        if not default_code:
            raise osv.except_osv(
                _('Error'), 
                _('No default code in product!'))

        bom_ids = False        
        for to in bom_code_split:  
            if len(default_code) <= to:
                continue
            partial = default_code[0:to]
            bom_ids = self.search(cr, uid, [
                ('bom_category', '=', 'half'), 
                ('product_id.default_code', '=', partial),
                ], context=context)
            if bom_ids:
                break
                
        if not bom_ids:
            raise osv.except_osv(
                _('Error'), 
                _('No default code in product!'))
                
        if len(bom_ids) > 1:
            _logger.error('Found more parent bom!')
                
        return self.write(cr, uid, ids, {
            'subparent_id': bom_ids[0],
            }, context=context)        
    
    _columns = {
        'subparent_id': fields.many2one(
            'mrp.bom', 'Sub parent bom'),        
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
