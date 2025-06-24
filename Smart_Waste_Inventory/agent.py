import os
import csv
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.cloud import storage
#sys.path.append(".")
from callback_logging import log_query_to_model, log_model_response
# Load environment variables
load_dotenv()

google_cloud_project = os.getenv("PROJECT_ID")
google_cloud_location = os.getenv("GOOGLE_CLOUD_LOCATION")
google_genai_use_vertexai = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "1")
model_name = os.getenv("MODEL")
bucket_name = os.getenv("BUCKET_NAME")
folder_path = "input" #change name according your folder name

# Tool: Get Inventory Data
def get_inventory(product_id: str) -> dict:
    """Fetch inventory records for a given product.
    Args:
        product_id (str)  : The id of the product for which to retrieve the inventory records. 
    Returns:
        dict: status and result or error msg.
    """
    filename = "inventory_data.csv"
    blob_name = f"{folder_path}/{filename}"
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    # Check if the blob (file) actually exists
    if not blob.exists():
        #print(f"Error: Object '{blob_name}' not found in bucket '{bucket_name}'.")
        return {"status": "error", "Exception": f"Error: Object '{blob_name}' not found in bucket '{bucket_name}'."}
    else:
        try:
            with blob.open(mode='r') as file:
                reader = csv.DictReader(file)
                if product_id:
                    return {"status": "success", "records": [row for row in reader if row["product_id"] == product_id]}
                else:
                    return {"status": "success", "records": [row for row in reader]}
        except Exception as e:
            return {"status": "error", "message": str(e)}

# Tool: Get Sales History
def get_saleshistory(product_id: str) -> dict:
    """Fetch historical sales data for a given product.
    Args:
        product_id (str)  : The id of the product for which to retrieve the sales data. 
    Returns:
        dict: status and result or error msg.
    """
    filename = "sales_data.csv"
    blob_name = f"{folder_path}/{filename}"
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
     # Check if the blob (file) actually exists
    if not blob.exists():
        #print(f"Error: Object '{blob_name}' not found in bucket '{bucket_name}'.")
        return {"status": "error", "Exception": f"Error: Object '{blob_name}' not found in bucket '{bucket_name}'."}
    else:
        try:
            with blob.open(mode='r') as file:
                reader = csv.DictReader(file)
                return {"status": "success", "records": [row for row in reader if row["product_id"] == product_id]}
        except Exception as e:
            return {"status": "error", "message": str(e)}

# Tool: Get Waste Records
def get_wasterecords(product_id: str) -> dict:
    """Fetch waste records for a given product.
    Args:
        product_id (str)  : The id of the product for which to retrieve the waste data. 
    Returns:
        dict: status and result or error msg.
    """
    filename = "waste_data.csv"
    blob_name = f"{folder_path}/{filename}"
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
     # Check if the blob (file) actually exists
    if not blob.exists():
        #print(f"Error: Object '{blob_name}' not found in bucket '{bucket_name}'.")
        return {"status": "error", "Exception": f"Error: Object '{blob_name}' not found in bucket '{bucket_name}'."}
    else:
        try:
            with blob.open(mode='r') as file:
                reader = csv.DictReader(file)
                return {"status": "success", "records": [row for row in reader if row["product_id"] == product_id]}
        except Exception as e:
            return {"status": "error", "message": str(e)}

# Tool: Get Weather Data
def get_weatherdata(store_id: str) -> dict:
    """Fetch weather data for a given store location.
    Args:
        store_id (str): The id of the store location for which to retrieve the weather data.
    Returns:
        dict: status and result or error msg.
    """
    filename = "weather_data.csv"
    blob_name = f"{folder_path}/{filename}"
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    # Check if the blob (file) actually exists
    if not blob.exists():
        return {"status": "error", "Exception": f"Error: Object '{blob_name}' not found in bucket '{bucket_name}'."}
    else:
        try:
            with blob.open(mode='r') as file:
                reader = csv.DictReader(file)
                return {"status": "success", "records": [row for row in reader if row["store_id"] == store_id]}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# Agent Definition
root_agent = Agent(
    name="Smart_Waste_Inventory_Agent",
    model=model_name,
    description="Analyzes inventory, sales, and waste data to forecast waste risk and inventory recommendations.",
    instruction="""
    You are a smart inventory and waste management assistant.
    Your goal is to help forecast waste risk score and cost impact of a single product (product name is the product id) or all products using inventory, sales, waste, and weather data.
    You also have the capability to recommend order quantities for a product by calculating its waste risk score and evaluating current usage.
    You have the capability to distinguish perishable and non-perishable products, if asked.
    You have the capability to determine the optimal storage temperature for each type of product, current storage temperature of a product is in sales data.
    You have access to tools that retrieve product related information, product name is the product id
    - always use get_inventory tool to fetch inventory data. Provide no product id while fetching data for all products
        (product_id, location_id, quantity, expiry_date, days_to_expiry, unit_cost, total_value)
    - always use get_saleshistory tool to fetch sales data for each product(product_id, store_id, date, units_sold, price, promotion_active, day_of_week, temperature)
    - always use get_wasterecords tool to fetch waste data for each product (store_id, date, product_id, waste_quantity, reason, disposal_method, waste_cost)
    - always use get_weatherdata tool to fetch Weather data for each store. All store locations for a product is available in the sales data
            -(store_id, date, temp_high, temp_low, precipitation, humidity, special_event)

    Use the following formulas and logic:

    1. Average Sales:
    - Calculate the mean of `units_sold` for the product over the past N days (e.g., 30 days) where N denotes the number of days for which the data is available

    2. Sales Volatility (30%):
    - Compute the standard deviation of `units_sold` over the same period.
    - Normalize as: `volatility_score = std_dev / average_sales`
    - If average_sales is zero, set volatility_score to zero.

    3. Weather Impact (20%):
    - product and location mapping is present in inventory data
    - For each location of the product
        - Correlate `units_sold` with `temperature`, `precipitation`, and `special_event`.
        - Use a weighted score:
        `weather_score = w1 * temp_effect + w2 * precip_effect + w3 * event_effect`
        where:
        - `temp_effect = 1 - (forecast_temp / optimal_temp)` if forecast_temp < optimal_temp, else 0
        - `precip_effect = precipitation / max_precipitation`
        - `event_effect = 1` if special_event is negative for sales, else 0
        - Default weights: w1=0.5, w2=0.3, w3=0.2 (adjust if historical data suggests otherwise)
    
    4. Days to Expiry (30%):
    - Normalize as: `expiry_score = 1 - (days_to_expiry / max_days_to_expiry)`
    - Higher score = fewer days remaining = higher risk.

    5. Inventory Surplus (20%):
    - Forecast sales before expiry: `forecasted_sales = average_sales * days_to_expiry`
    - Surplus = `max(0, current_inventory - forecasted_sales)`
    - Normalize surplus as a risk score: `surplus_score = surplus / current_inventory` (if current_inventory > 0)

    6. Waste Risk Score (100%):
    - Combine all components:
        Waste Risk Score = 
        0.30 * expiry_score +
        0.30 * volatility_score +
        0.20 * weather_score +
        0.20 * surplus_score

    7. Projected Waste Quantity:
    - `projected_waste = max(0, current_inventory - forecasted_sales)`

    8. Waste Cost Impact:
    - waste_cost = projected_waste * (unit_cost + disposal_cost - salvage_value)
    Where:
    - projected_waste = max(0, current_inventory - forecasted_sales)
    - unit_cost = cost per unit from inventory data
    - `waste_cost = projected_waste * (unit_cost + disposal_cost - salvage_value)`
    - If `disposal_cost` is missing, estimate as:
        - `disposal_cost = base_disposal_fee + (projected_waste * disposal_rate_per_unit)`
        - Use defaults: base_disposal_fee = ₹50, disposal_rate_per_unit = ₹2/unit
    - If `salvage_value` is missing, estimate as:
        - `salvage_value = resale_price_per_unit * salvage_probability`
        - Use defaults: resale_price_per_unit = 0.3 * unit_cost, salvage_probability = 0.3

    **General Guidance:**
    - You always check for missing or invalid data. If any required data is unavailable, inform the user clearly and suggest what is needed.
    - You should always use recent, available and relevant data for all calculations.
    - When making estimates, state your assumptions and the default values used.
    - Always compute the Final waste risk score should be an average of multiple scores.
    - Use your knowledge base when asked to make recommedations on optimal storage temperatures for any product.
    - Present result as a scorecard with clear explanations and, where possible, actionable recommendations.

    If any tool fails or data is missing, inform the user politely and suggest corrective steps.
    """,
    after_model_callback=log_model_response,
    tools=[get_inventory, get_saleshistory, get_wasterecords, get_weatherdata]
)