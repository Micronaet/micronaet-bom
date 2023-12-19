# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP)
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
# Developer: Nicola Riolini @thebrush (<https://it.linkedin.com/in/thebrush>)
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import os
import pdb
import sys
import xlrd
import erppeek
import ConfigParser


# -----------------------------------------------------------------------------
# Parameters:
# -----------------------------------------------------------------------------
# Stagione attuale: 2023-24
from_date = '2022-09-01'
to_date = '2023-08-31'

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
cfg_file = os.path.expanduser('../openerp.cfg')

config = ConfigParser.ConfigParser()
config.read([cfg_file])
dbname = config.get('dbaccess', 'dbname')
user = config.get('dbaccess', 'user')
pwd = config.get('dbaccess', 'pwd')
server = config.get('dbaccess', 'server')
port = config.get('dbaccess', 'port')   # verify if it's necessary: getint


# -----------------------------------------------------------------------------
# Connect to ODOO:
# -----------------------------------------------------------------------------
odoo = erppeek.Client(
    'http://%s:%s' % (
        server, port),
    db=dbname,
    user=user,
    password=pwd,
    )
picking_pool = odoo.model('stock.picking')
move_pool = odoo.model('stock.move')
product_pool = odoo.model('product.product')

log_f = open('./fabric_detail.csv', 'w')
product_update = {}


# -----------------------------------------------------------------------------
# MRP unload component:
# -----------------------------------------------------------------------------

filename = '/tmp/mrp_last_year.xlsx'
odoo.context = {
    'run_force': {
        'from_date': from_date,
        'to_date': to_date,
        'filename': filename,
        'update': False,  # Only dry run!
        }}

mrp_pool = odoo.model('mrp.production')
mrp_unload = mrp_pool.schedule_unload_mrp_material(from_date)
pdb.set_trace()

for product_id, unload in mrp_unload.iteritems():
    if product_id not in product_update:
        product_update[product_id] = [0.0, 0.0]  # Car, Scar
    product_update[product_id][1] += unload
pdb.set_trace()

# -----------------------------------------------------------------------------
# Load TCAR / TSCAR:
# -----------------------------------------------------------------------------
in_ids = move_pool.search([
    ('picking_id', '!=', False),
    ('picking_id.origin', '=ilike', 'OF%'),
    ('picking_id.date', '>=', '%s 00:00:00' % from_date),
    ('picking_id.date', '<=', '%s 23:59:59' % to_date),
    # ('product_id.inventory_category_id.name', '=', 'Tessuti'),
    ('state', '=', 'done'),
    ])

# Pipe unload
out_ids = move_pool.search([
    ('picking_id', '!=', False),
    ('picking_id.dep_mode', '=', 'workshop'),
    ('picking_id.date', '>=', '%s 00:00:00' % from_date),
    ('picking_id.date', '<=', '%s 23:59:59' % to_date),
    ('product_id.inventory_category_id.name', '=', 'Tubi'),
    ('state', '=', 'done'),
    ])

# move.picking_id.location_dest_id.name == 'Stock'
# Setup loop data:
loop = [
    (1, 'in', in_ids),
    (0, 'out', out_ids),
    ]

log_f.write('Codice|Modo|SCAR|CAR|Picking|Data|Note\n')
for pos, mode, move_ids in loop:
    counter = 0
    total = len(move_ids)
    for move in move_pool.browse(move_ids):
        counter += 1
        product = move.product_id
        default_code = (product.default_code or '').upper()
        quantity = move.product_qty
        if mode == 'in':
            tcar = quantity
            tscar = 0.0
        else:
            tcar = 0.0
            tscar = quantity

        picking = move.picking_id
        picking_name = '%s - %s' % (picking.name, picking.origin or '')
        if not default_code:
            print('%s. %s su %s [ERROR] %s' % (
                mode, counter, total, default_code))
            log_f.write('%s|%s|%s|%s|%s|%s|%s\n' % (
                default_code, mode, tscar, tcar, picking_name, picking.date,
                'ERROR'))
            log_f.flush()
            continue

        print('%s. %s su %s [INFO] %s' % (
            mode, counter, total, default_code))
        log_f.write('%s|%s|%s|%s|%s|%s|%s\n' % (
            default_code, mode, tscar, tcar, picking_name, picking.date, 'OK'))
        log_f.flush()
        product_id = product.id
        if product_id not in product_update:
            product_update[product_id] = [0.0, 0.0]  # tcar, tscar
        product_update[product_id][pos] += quantity

# -----------------------------------------------------------------------------
# Clean TSCAR TCAR data:
# -----------------------------------------------------------------------------
product_ids = product_pool.search([
    ('inventory_category_id.name', '!=', 'Tessuti'),
    ])

pdb.set_trace()
for product in product_pool.browse(product_ids):
    product_pool.write([product.id], {
        'old_tscar': 0.0,
        'old_tcar': 0.0,
        })

# -----------------------------------------------------------------------------
# Update product:
# -----------------------------------------------------------------------------
pdb.set_trace()
for product_id in product_update:
    tcar, tscar = product_update[product_id]
    print('ID: %s [SCAR %s] [TCAR %s]' % (product_id, tscar, tcar))
    product_pool.write([product_id], {
        'old_tscar': tscar,
        'old_tcar': tcar,
        })

log_f = open('./fabric_result.csv', 'w')
log_f.write('Codice|TSCAR|TCAR\n')
for product in product_pool.browse(product_ids):
    log_f.write('%s|%s|%s\n' % (
        product.default_code,
        product.old_tscar,
        product.old_tcar),
    )
