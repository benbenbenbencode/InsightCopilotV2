select
    product_id,
    product_name,
    product_type,
    min_amount,
    max_amount,
    tenor_options
from {{ source('raw', 'raw_products') }}
