import io
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import bigquery
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, Any

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React app's address
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Welcome to the Inventory Uploader API"}

@app.get("/ping")
async def ping():
    return {"ping": "pong"}

@app.post("/upload_inventory")
async def upload_inventory(
    file: UploadFile = File(...),
    column_mapping: Optional[str] = Form(None)
):
    """
    Upload inventory CSV with flexible column mapping.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV file.")

    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
        available_columns = list(df.columns)
        if not column_mapping:
            auto_mapping = {}
            sku_variations = ['sku_id', 'sku', 'product_id', 'id', 'item_id', 'product_code']
            for col in available_columns:
                if col.lower() in [v.lower() for v in sku_variations]:
                    auto_mapping[col] = 'sku_id'
                    break
            name_variations = ['name', 'product_name', 'item_name', 'description', 'title']
            for col in available_columns:
                if col.lower() in [v.lower() for v in name_variations]:
                    auto_mapping[col] = 'name'
                    break
            stock_variations = ['stock', 'quantity', 'quantity_on_hand', 'inventory', 'available']
            for col in available_columns:
                if col.lower() in [v.lower() for v in stock_variations]:
                    auto_mapping[col] = 'stock'
                    break
            date_variations = ['last_updated', 'updated_at', 'modified', 'timestamp', 'date']
            for col in available_columns:
                if col.lower() in [v.lower() for v in date_variations]:
                    auto_mapping[col] = 'last_updated'
                    break
            required_columns = {'sku_id', 'name', 'stock', 'last_updated'}
            if not required_columns.issubset(set(auto_mapping.values())):
                return {
                    "message": "Column mapping required",
                    "available_columns": available_columns,
                    "required_columns": list(required_columns),
                    "auto_detected_mapping": auto_mapping,
                    "missing_columns": list(required_columns - set(auto_mapping.values()))
                }
            column_mapping = auto_mapping
        else:
            import json
            try:
                column_mapping = json.loads(column_mapping)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid column mapping JSON format")
        required_columns = {'sku_id', 'name', 'stock', 'last_updated'}
        mapped_columns = set(column_mapping.values())
        if not required_columns.issubset(mapped_columns):
            missing = required_columns - mapped_columns
            raise HTTPException(status_code=400, detail=f"Missing required column mappings: {missing}")
        source_columns = set(column_mapping.keys())
        if not source_columns.issubset(set(available_columns)):
            missing = source_columns - set(available_columns)
            raise HTTPException(status_code=400, detail=f"Column mapping references non-existent columns: {missing}")
        df_mapped = df.rename(columns=column_mapping)
        df_final = df_mapped[list(required_columns)]
        df_final['stock'] = pd.to_numeric(df_final['stock'], errors='coerce')
        df_final['stock'] = df_final['stock'].fillna(0)
        try:
            df_final['last_updated'] = pd.to_datetime(df_final['last_updated'])
        except:
            df_final['last_updated'] = datetime.now()
        client = bigquery.Client(project="walis-inventory-mvp")
        table_id = "walis-inventory-mvp.warehouse_data.inventory"
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,
            autodetect=True,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )
        job = client.load_table_from_dataframe(df_final, table_id, job_config=job_config)
        job.result()
        return {
            "message": f"File '{file.filename}' uploaded and data ingested successfully.",
            "rows_processed": len(df_final),
            "column_mapping_used": column_mapping,
            "final_columns": list(df_final.columns)
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest data to BigQuery: {e}")

@app.post("/upload_orders")
async def upload_orders(
    file: UploadFile = File(...),
    column_mapping: Optional[str] = Form(None)
):
    """
    Upload orders CSV with flexible column mapping.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV file.")
    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
        available_columns = list(df.columns)
        if not column_mapping:
            auto_mapping = {}
            order_id_variations = ['order_id', 'id', 'order', 'order_number']
            sku_variations = ['sku_id', 'sku', 'product_id', 'item_id']
            quantity_variations = ['quantity', 'qty', 'amount', 'count']
            order_date_variations = ['order_date', 'date', 'created_at', 'timestamp']
            customer_id_variations = ['customer_id', 'customer', 'buyer_id', 'client_id']
            for col in available_columns:
                if col.lower() in [v.lower() for v in order_id_variations]:
                    auto_mapping[col] = 'order_id'
                if col.lower() in [v.lower() for v in sku_variations]:
                    auto_mapping[col] = 'sku_id'
                if col.lower() in [v.lower() for v in quantity_variations]:
                    auto_mapping[col] = 'quantity'
                if col.lower() in [v.lower() for v in order_date_variations]:
                    auto_mapping[col] = 'order_date'
                if col.lower() in [v.lower() for v in customer_id_variations]:
                    auto_mapping[col] = 'customer_id'
            required_columns = {'order_id', 'sku_id', 'quantity', 'order_date', 'customer_id'}
            if not required_columns.issubset(set(auto_mapping.values())):
                return {
                    "message": "Column mapping required",
                    "available_columns": available_columns,
                    "required_columns": list(required_columns),
                    "auto_detected_mapping": auto_mapping,
                    "missing_columns": list(required_columns - set(auto_mapping.values()))
                }
            column_mapping = auto_mapping
        else:
            import json
            try:
                column_mapping = json.loads(column_mapping)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid column mapping JSON format")
        required_columns = {'order_id', 'sku_id', 'quantity', 'order_date', 'customer_id'}
        mapped_columns = set(column_mapping.values())
        if not required_columns.issubset(mapped_columns):
            missing = required_columns - mapped_columns
            raise HTTPException(status_code=400, detail=f"Missing required column mappings: {missing}")
        source_columns = set(column_mapping.keys())
        if not source_columns.issubset(set(available_columns)):
            missing = source_columns - set(available_columns)
            raise HTTPException(status_code=400, detail=f"Column mapping references non-existent columns: {missing}")
        df_mapped = df.rename(columns=column_mapping)
        df_final = df_mapped[list(required_columns)]
        df_final['quantity'] = pd.to_numeric(df_final['quantity'], errors='coerce')
        df_final['quantity'] = df_final['quantity'].fillna(0)
        try:
            df_final['order_date'] = pd.to_datetime(df_final['order_date'])
        except:
            df_final['order_date'] = datetime.now()
        client = bigquery.Client(project="walis-inventory-mvp")
        table_id = "walis-inventory-mvp.warehouse_data.orders"
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,
            autodetect=True,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )
        job = client.load_table_from_dataframe(df_final, table_id, job_config=job_config)
        job.result()
        return {
            "message": f"File '{file.filename}' uploaded and data ingested successfully.",
            "rows_processed": len(df_final),
            "column_mapping_used": column_mapping,
            "final_columns": list(df_final.columns)
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest data to BigQuery: {e}")

@app.post("/calculate-stockouts")
async def calculate_stockouts():
    """
    Calculate stockouts by comparing inventory quantity_on_hand with sum of orders quantity.
    For every inventory.quantity_on_hand < sum(orders.quantity), it's a stockout.
    Store results in 'current_stockouts' table.
    """
    try:
        client = bigquery.Client(project="walis-inventory-mvp")
        
        # SQL query to calculate stockouts
        stockout_query = """
        WITH inventory_data AS (
            SELECT 
                sku_id,
                name,
                quantity_on_hand,
                last_updated
            FROM `walis-inventory-mvp.warehouse_data.inventory`
        ),
        orders_summary AS (
            SELECT 
                sku_id,
                SUM(quantity) as total_ordered_quantity
            FROM `walis-inventory-mvp.warehouse_data.orders`
            GROUP BY sku_id
        ),
        stockout_calculation AS (
            SELECT 
                i.sku_id,
                i.name,
                i.quantity_on_hand,
                COALESCE(o.total_ordered_quantity, 0) as total_ordered_quantity,
                (i.quantity_on_hand - COALESCE(o.total_ordered_quantity, 0)) as remaining_quantity,
                CASE 
                    WHEN i.quantity_on_hand < COALESCE(o.total_ordered_quantity, 0) THEN TRUE
                    ELSE FALSE
                END as is_stockout,
                i.last_updated,
                CURRENT_TIMESTAMP() as calculation_timestamp
            FROM inventory_data i
            LEFT JOIN orders_summary o ON i.sku_id = o.sku_id
        )
        SELECT 
            sku_id,
            name,
            quantity_on_hand,
            total_ordered_quantity,
            remaining_quantity,
            is_stockout,
            last_updated,
            calculation_timestamp
        FROM stockout_calculation
        WHERE is_stockout = TRUE
        ORDER BY remaining_quantity ASC
        """
        
        # Execute the query
        query_job = client.query(stockout_query)
        results = query_job.result()
        
        # Convert results to DataFrame
        stockout_data = []
        for row in results:
            stockout_data.append({
                'sku_id': row.sku_id,
                'name': row.name,
                'quantity_on_hand': row.quantity_on_hand,
                'total_ordered_quantity': row.total_ordered_quantity,
                'remaining_quantity': row.remaining_quantity,
                'is_stockout': row.is_stockout,
                'last_updated': row.last_updated,
                'calculation_timestamp': row.calculation_timestamp
            })
        
        if not stockout_data:
            return {
                "message": "No stockouts found. All inventory levels are sufficient for current orders.",
                "stockout_count": 0,
                "stockouts": []
            }
        
        # Create DataFrame and upload to BigQuery
        df = pd.DataFrame(stockout_data)
        
        # Define the stockout table
        stockout_table_id = "walis-inventory-mvp.warehouse_data.current_stockouts"
        
        # Configure job to overwrite the table (replace existing data)
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV,
            autodetect=True,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,  # Replace existing data
        )
        
        # Upload stockout data to BigQuery
        job = client.load_table_from_dataframe(df, stockout_table_id, job_config=job_config)
        job.result()  # Wait for the job to complete
        
        return {
            "message": f"Stockout calculation completed successfully. {len(stockout_data)} items found to be out of stock.",
            "stockout_count": len(stockout_data),
            "stockouts": stockout_data,
            "table_updated": stockout_table_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate stockouts: {e}")

@app.get("/stockouts")
async def get_stockouts():
    """
    Retrieve current stockout data from the current_stockouts table.
    """
    try:
        client = bigquery.Client(project="walis-inventory-mvp")
        
        query = """
        SELECT 
            sku_id,
            name,
            quantity_on_hand,
            total_ordered_quantity,
            remaining_quantity,
            is_stockout,
            last_updated,
            calculation_timestamp
        FROM `walis-inventory-mvp.warehouse_data.current_stockouts`
        ORDER BY remaining_quantity ASC
        """
        
        query_job = client.query(query)
        results = query_job.result()
        
        stockouts = []
        for row in results:
            stockouts.append({
                'sku_id': row.sku_id,
                'name': row.name,
                'quantity_on_hand': row.quantity_on_hand,
                'total_ordered_quantity': row.total_ordered_quantity,
                'remaining_quantity': row.remaining_quantity,
                'is_stockout': row.is_stockout,
                'last_updated': row.last_updated,
                'calculation_timestamp': row.calculation_timestamp
            })
        
        return {
            "stockout_count": len(stockouts),
            "stockouts": stockouts
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve stockouts: {e}") 