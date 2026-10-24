{#
  By default dbt names schemas "<target>_<custom>" (e.g. public_staging).
  We want the exact names of our warehouse layers: staging, marts, reference.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name if custom_schema_name is not none else target.schema }}
{%- endmacro %}
