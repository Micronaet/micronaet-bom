update product_product set structure_id=1 where id in (SELECT distinct id 
    FROM product_product
    WHERE 
        product_tmpl_id in (
            SELECT product_tmpl_id 
            FROM mrp_bom 
            WHERE bom_category = 'product') );

