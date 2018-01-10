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

{
    'name': 'Order BOM explode report',
    'version': '0.1',
    'category': 'Report',
    'description': '''
        Manage report for order product
        ''',
    'author': 'Micronaet S.r.l. - Nicola Riolini',
    'website': 'http://www.micronaet.it',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'product',
        'sale',
        'purchase',
        'mrp',
        'report_aeroo',
        'order_bom',
        'bom_category', 
        'inventory_field', # for inventory field
        'bom_order_utility', # Utility for filter
        'bom_dynamic_structured', # for filter type category
        'textilene_status', # TODO remove when moved company parameters
        'production_accounting_external',
        'production_forecast_order', # for forecast check
        'no_parcels_count', # exclude no parcels product        
        'product_last_supplier', # last purchase supplier data (for filter)
        ],
    'init_xml': [],
    'demo': [],
    'data': [
        #'security/xml_groups.xml',
        #'security/ir.model.access.csv',        
        
        'bom_explode_view.xml',
        'report/explode_report.xml',
        'wizard/report_component_status.xml',
        #'scheduler.xml',
        ],
    'active': False,
    'installable': True,
    'auto_install': False,
    }
