-- sql_models/fct_order_lines_enriched.sql

SELECT
  order_line_id,
  order_id,
  purchase_date,
  customer_id,
  customer_name,
  customer_state,
  loyalty_tier,
  product_id,
  product_name,
  category,
  subcategory,
  brand,
  quantity,
  unit_price,
  discount_pct,
  gross_amount,
  discount_amount,
  revenue,
  channel,
  payment_method,
  store
FROM `da-aaa-aca.curated_models_enriched.fct_order_lines_enriched`;