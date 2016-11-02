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

        empty_hw = []  
        mt_new = []

        for item in ids: #product_ids: # XXX ids:
            self.migrate_assign_product_bom_product1(
                cr, uid, [item], empty_hw, mt_new, context=context)
            self.write(cr, uid, item, {
                'bom_category': 'done',
                }, context=context) 
        log_f.write('%s' % (empty_hw,))    
        log_f.write('%s' % (mt_new,))    
        log_f.close()        
        return True    
        
    def migrate_assign_product_bom_product1(self, cr, uid, ids, 
            empty_hw, mt_new, context=None):
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
            _logger.error('%s. No dynamic bom structure' % ( 
                bom_proxy.id,
                ))
            return
                    
        # ---------------------------------------------------------------------
        # Create dynamic mask from code:
        # ---------------------------------------------------------------------
        categ_id = {
            'TL': 26, # Tela
            'PO': 27, # Poggiatesta
            'PA': 19, # Parasole #XXX non correct
            'PV': 28, # Tondino
            'MT': 29, # Materassino
            }
        code_map = {
            #Parent:Tela
            '005': '205',            
            '014': '024',
            '023': '123',
            '025': '024', # Aggiunto oggi
            '026': '127',
            '027': '127',
            '028': '128',
            '029': '129',
            '030': '130',
            '031': '131',
            '032': '132',
            '034': '135', # parasole
            '035': '135',
            '036': '135',
            '039': '135', # parasole
            '045': '145',
            '046': '145', # Inidicazione Davide 20 ott (ha consumi diversi)
            '048': '145',
            '049': '145',
            '051': '050', # parasole e poggiatesta
            #'071': '070', # parasole # Rimosso su indicazione di Davide
            '121': '021',
            '124': '024',
            '126': '127',
            '136': '135',
            '148': '145',
            '149': '145',
            '170': '070',
            '171': '070', # parasole
            '235': '230',
            #'552': '550', # Rimosso su indicazione di Davide
            '905': '900',
            '935': '930',
            '936': '931',
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
            # Materassino: 
            'TSK': 'MT',
            'T3D': 'MT',
            }
             
        code6_map = {
            # TODO 
            #'TL127S': 'TL127PO'
            }

        crea_hw = {
            #'014', '024', '025', '124', 
            # '230'
            '046': [('TL145', 'TEX150', 1.08), ('PO650', 'TEX165', 0.21)],
            '049': [('TL145', 'TEX150', 1.12), ('PO650', 'TEX165', 0.21)],
            '149': [('TL145', 'TEX150', 1.12), ('PO650', 'TEX165', 0.21)],            
            '050': [('TL038', 'TEX165', 2.3), ('PA601', 'TEX150', 0.4)],
            '051': [('TL038', 'TEX165', 2.3), ('PA601', 'TEX150', 0.4), ('PO651', 'TEX165', 0.22)],
            # TODO TX o PE
            # VEDERE XXX '034': [('TL135', 'TESPOL150', 1.05), ('PA600', 'TESPOL165', 0.22)],
            # VEDERE '039': [('TL135', 'TEX150', 1.05), ('PA600', 'TEX165', 0.22)],
            
            # 700
            # 701            
            
            # 550 
            # 552            
            
            # 'G421': ['TLG420', 'PA600']
            }
            
        # XXX SOLO INDICATIVO PER FORMALIZZARE LE REGOLE:
        tessuto_con_doppione = [
            '014', # unire
            '024', # unire
            '025', # unire
            '027', '029',
            '034', # TL135 >, PA600 <
            '035', '036',
            '039', # TL135 >, PA600 <
            '046', # TL145 >, PO650 <
            '048',
            '049', # TL145 >, PO650 <
            '050', # TL038 >, PA601 < 
            '051', # TL038 >, PA601 < (è 050) + PO651 0.22
            '052', #
            #'070', # Non più come 071
            #'071', # Non più come 070
            '090', '121',
            '124', # unire
            '127', '128', '129', '130', '131', '132', '135', '145', '148',
            '149', # TL145 >, PO650 <
            '150', '190', '205', '206',
            '230', # unire
            '550', # Non più come 552
            '552', # Non più come 550
            '810', '900', '905',
            # 'G241', # ??? TLG420, PA600
            ] 
        
        # Product and Halfworked    
        direct_sale = {
            # Parasoli
            '601': 'PA', 
            '600': 'PA', 
            # Poggiatesta / Cuscino
            '650': 'PO', 
            '651': 'PO', 
            '630': 'PO', 
            '649': 'PO',
            # Supporti:
            '620': 'SU',
            }
            
        # Default code:    
        default_code = bom_proxy.product_id.default_code        
        if not default_code:
            _logger.error('ID %s. No product code' % bom_proxy.id)
            return 
        default_code = default_code.upper()
        
        # Mask for S or not S (same)
        if default_code[12:13] == 'S':
            dynamic_mask = default_code[:12] + '%'
        else:
            dynamic_mask = default_code + '%'

        # ---------------------------------------------------------------------
        # Create TL element:
        # ---------------------------------------------------------------------        
        for line in bom_proxy.bom_line_ids:
            if default_code.startswith('MT'):
                _logger.warning('Code %s. Jump MT' % (
                    default_code))
                if default_code not in mt_new:
                    mt_new.append(default_code)    
                return 
        
            # Component code:
            component_code = line.product_id.default_code
            if not component_code:
                _logger.error('Code %s.%s Empty component code' % (
                    default_code, line.id))
                return
            component_code = component_code.upper()
            
            # Type code:
            #type_code = 'TL'
            
            # Parent code:
            parent = default_code[:3]
            if parent in direct_sale:
                parent_code = ''
                type_code = '%s%s' % (direct_sale[parent], default_code)
            elif parent in ('810', '081', '085'):
                type_code = 'PVC6LU'
                parent_code = ''
            elif parent in ('084', ):
                type_code = 'PVC6OP'
                parent_code = ''
            else: 
                # Default code:    
                parent_code = code_map.get(parent, parent)
                type_code = type_map.get(component_code[:3], False)

            if not type_code:
                _logger.error('Code %s.%s Non MT TL PO PA' % (
                    default_code, line.id))
                return
                            
            #Fabric code:
            if parent in ('810', '081', '085', '084') or parent in direct_sale:
                fabric_code = ''
            else:
                # Default code:                
                if 'B' in default_code[4:6]:
                    fabric_code = default_code[3:6].replace('B', ' ')
                else:    
                    fabric_code = default_code[3:6]

            # Color code        
            if parent in direct_sale:
                color_code = ''
            else:    
                color_code = default_code[8:12].strip()
            if len(color_code) == 1:
                _logger.error('Code %s.%s Colore 1 carattere %s' % (
                    default_code, line.id, component_code))
                return
            
            # TODO Decidere se creare il solo semilavorato oppure continuare
            HW_codes = []
            if parent in crea_hw:
                for hw, component, qty in crea_hw[parent]:
                    HW_code = '%s%s%s' % (
                        hw, fabric_code, color_code)
                    fabric_product = '%s%s' % (
                        component, color_code)
                    # Search fabric:
                    fabric_ids = product_pool.search(cr, uid, [
                        ('default_code', '=', fabric_product)], context=context)    
                    if fabric_ids:
                        fabric_id = fabric_ids[0]
                    else:
                        fabric_id = product_pool.create(cr, uid, {
                            'name': fabric_product,
                            'default_code': fabric_product,
                            'uom_id': 8, # mt
                            'uos_id': 8, # mt
                            'uom_po_id': 8, # mt                            
                            }, context=context)
                        _logger.warning('Create fabric: %s' % fabric_product)

                    fabric_proxy = product_pool.browse(
                        cr, uid, fabric_id, context=context)
                            
                    HW_codes.append((
                        HW_code, 
                        fabric_proxy.id,
                        fabric_proxy.uom_id.id,
                        qty,
                        ))

                    if HW_code not in empty_hw:
                        empty_hw.append(HW_code)                        
            else:                
                # Normal creation:
                HW_codes = [
                    ('%s%s%s%s' % (
                        type_code or '??',
                        parent_code,
                        fabric_code, 
                        color_code,
                        ), 
                    line.product_id.id, # fabric_id    
                    line.product_uom.id, # fabric_uom
                    line.product_qty,
                    )]
                        
            for HW_code, fabric_id, fabric_uom, product_qty in HW_codes:
                if parent in direct_sale: # use TL for PA and PO from Direct s.
                    category_id = categ_id.get('TL', False)
                else:    
                    category_id = categ_id.get(HW_code[:2], False)
                    
                if not category_id:
                    _logger.error('Code %s.%s No BOM categ. : %s' % (
                        default_code, line.id, HW_code))
                    return            
            
                component_ids = product_pool.search(cr, uid, [
                    ('default_code', '=', HW_code),
                    ('relative_type', '=', 'half'),
                    ], context=context)

                if component_ids:
                    if len(component_ids) > 1:
                        _logger.error += 'Code %s.%s More product HW %s' % (
                            default_code, line.id, component_code)
                    HW_id = component_ids[0]
                    create = False
                else:
                    create = True
                    HW_id = product_pool.create(cr, uid, {
                        'name': HW_code,
                        'default_code': HW_code,
                        'relative_type': 'half',       
                        'structure_id': structure_id,
                        'uom_id': 1, # XXX NR
                        'ean13_auto': False, # XXX
                        }, context=context)
             
                # -------------------------------------------------------------
                # Create / Update fabric under HW component
                # -------------------------------------------------------------
                HW_proxy = product_pool.browse(cr, uid, HW_id, context=context)
                if not HW_proxy.half_bom_id: # Button and reload data
                    # Only first element
                    product_pool.create_product_half_bom(
                        cr, uid, [HW_id], context=context)
                    HW_proxy = product_pool.browse(
                        cr, uid, HW_id, context=context)                
                    line_pool.create(cr, uid, {
                        # Link:
                        'bom_id': HW_proxy.half_bom_id.id, # bom link
                        'halfwork_id': HW_proxy.id, # product link
                        
                        # Fabric data:
                        'product_id': fabric_id, 
                        'product_uom': fabric_uom, 
                        'type': line.type,
                        'product_qty': product_qty,
                        }, context=context)

                # -------------------------------------------------------------
                # Create / Update rule in dynamic:
                # -------------------------------------------------------------
                line_ids = line_pool.search(cr, uid, [
                    ('bom_id', '=', dynamic_bom_id), # dynamic bom for structure
                    ('dynamic_mask', '=', dynamic_mask), # mask
                    ('category_id', '=', category_id),
                    ('product_id', '=', HW_proxy.id),
                    ], context=context)
                if not line_ids: # Update or check
                    line_pool.create(cr, uid, {
                        'bom_id': dynamic_bom_id,
                        'dynamic_mask': dynamic_mask,
                        'category_id': category_id,
                        'product_id': HW_proxy.id, 
                        'product_uom': HW_proxy.uom_id.id, 
                        'product_qty': 1, # always!
                        'type': 'normal',
                        }, context=context)
        return

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
