from datetime import datetime
import re
import apache_beam as beam
from apache_beam.io import ReadFromParquet, WriteToBigQuery
from apache_beam.options.pipeline_options import PipelineOptions, GoogleCloudOptions, StandardOptions
import uuid

# Crear las opciones de pipeline
options = PipelineOptions()

# Configuración para Google Cloud
google_cloud_options = options.view_as(GoogleCloudOptions)
google_cloud_options.project = 'yelp-412816'
google_cloud_options.job_name = f'pipeline-clean-data-{str(uuid.uuid4())}'
google_cloud_options.staging_location = 'gs://proyecto_yelp/staging'
google_cloud_options.temp_location = 'gs://proyecto_yelp/temp'
google_cloud_options.region = 'us-central1'
options.view_as(StandardOptions).runner = 'DataflowRunner'

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------


# Funciones de limpieza y procesamiento de datos
def format_strings(row):
    string_columns = ["name", "address", "city", "state", "attributes", "categories", "Days", "Hours"]

    for column in string_columns:
        if row.get(column):
            row[column] = row[column].lower().capitalize()

    return row

def drop_duplicates(row):
    columns_to_check = ["business_id", "name", "address", "city", "state", "postal_code",
                        "latitude", "longitude", "stars", "review_count", "attributes", "categories", "Days", "Hours"]
    
    key = "|".join(str(row[column]) if row[column] is not None else "" for column in columns_to_check)
    
    if key in drop_duplicates.seen_keys:
        return None
    else:
        drop_duplicates.seen_keys.add(key)
        return row

drop_duplicates.seen_keys = set()

def round_numeric_values(row):
    if row.get('latitude') is not None:
        row['latitude'] = round(row['latitude'])
    if row.get('longitude') is not None:
        row['longitude'] = round(row['longitude'])
    if row.get('stars') is not None:
        row['stars'] = round(row['stars'])
    if row.get('review_count') is not None:
        row['review_count'] = round(row['review_count'])
    return row

def separate_text(row):
    if 'attributes' in row:
        if row['attributes'] is not None:
            separated_text = re.sub(r'([a-z])([A-Z])', r'\1 \2', row['attributes'])
            row['attributes'] = separated_text
    return row
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Crear el pipeline
with beam.Pipeline(options=options) as p:
    data_from_storage = (
        p
        | "ReadData" >> ReadFromParquet("gs://proyecto_yelp/data_new/Busisness.parquet")
    )

    # Procesar los datos en base a las funciones
    processed_data = (
        data_from_storage
        
        | "FormatStrings" >> beam.Map(format_strings)  
        | "DropDuplicates" >> beam.Map(drop_duplicates)
        | "round_numeric_values" >> beam.Map(round_numeric_values)
        | "SeparateText" >> beam.Map(lambda row: {key: separate_text(value) if key == 'attributes' else value for key, value in row.items()})
    )

    # esquema de BigQuery
    bq_schema = {
        "fields": [
            {"name": "business_id", "type": "STRING"},
            {"name": "name", "type": "STRING"},
            {"name": "address", "type": "STRING"},
            {"name": "city", "type": "STRING"},
            {"name": "states", "type": "STRING"},
            {"name": "postal_code", "type": "STRING"},
            {"name": "latitude", "type": "STRING"},
            {"name": "longitude", "type": "STRING"},
            {"name": "stars", "type": "FLOAT"},
            {"name": "review_count", "type": "INTEGER"},
            {"name": "attribute", "type": "STRING"},
            {"name": "categories", "type": "STRING"},
            {"name": "day", "type": "STRING"},
            {"name": "hour", "type": "STRING"}
        ]
    }

    table_name = "yelp_busisness"

    processed_data | "WriteToBigQuery" >> WriteToBigQuery(
        table=table_name,
        dataset='db',  
        schema=bq_schema,
        create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
        write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND
    )
