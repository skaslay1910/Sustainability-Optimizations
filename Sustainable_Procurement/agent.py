import os
import asyncio
import sys
import requests
import json
import csv
from datetime import datetime
import logging
import google.cloud.logging
import vertexai
from vertexai import agent_engines

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.sessions import InMemorySessionService
from google.genai import types
from typing import Optional, List, Dict

from google.adk.tools.tool_context import ToolContext
from google.cloud import storage
from google.adk.runners import Runner
sys.path.append(".")
from callback_logging import log_query_to_model, log_model_response
load_dotenv()
google_cloud_project = os.getenv("PROJECT_ID")
google_cloud_location = os.getenv("GOOGLE_CLOUD_LOCATION")
google_genai_use_vertexai = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "1")

model_name = os.getenv("MODEL")
bucket_name = os.getenv("BUCKET_NAME")
folder_path = "input"

api_config = os.getenv("API_CONFIG")

# Initialize Vertex AI with the correct project and location
vertexai.init(
    project=google_cloud_project,
    location=google_cloud_location,
    staging_bucket=bucket_name,
)

#Fetch function to read the supplier list

def get_vendor_list(product_id: str, location: str) ->dict:
    """Returns the list of suppliers for a specified product and a given location (optional).
    Args:
        product_id (str)  : The id of the product for which to retrieve the list of suppliers. 
        location (str) : The name of the country from where to procure the product.
    
        Returns:
        dict: status and result or error msg.
    """
    filename = 'suppliers.csv'
    #file_path = f"gs://{bucket_name}/{folder_path}/{filename}"
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
            #with open(file_path, mode='r') as file:
            with blob.open(mode="r") as file:
            
                reader = csv.DictReader(file)  # Reads the file as a dictionary
                if location:
                    matching_records = [row for row in reader if row["product_id"] == product_id and row["location"] == location]
                    return {"status": "success", "matchingrecords": matching_records} 
                else:
                    return {"status": "success", "matchingrecords": [row for row in reader if row["product_id"] == product_id]  }
                    
        except FileNotFoundError as e:
            return {"status": "error", "Exception": e}
            
#Fetch function to get the supplier certifications
def get_supplier_certifications(supplier_id: str) -> dict:
    """Returns the list of certifications for a specified supplier.
    Args:
        supplier_id (str)  : The id of the supplier for whom to retrieve the list of certifications and their validity. 
    Returns:
        dict: status and result or error msg.
    """
    filename = 'Supplier_Certifications.csv'
    
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
                reader = csv.DictReader(file)  # Reads the file as a dictionary
                return {"status": "success", "matchingrecords": [row for row in reader if row["supplier_id"] == supplier_id] }
      
        except Exception as e:
            return {"status": "error", "Exception": e}

#Fetch function to get the supplier emissions
def get_supplier_emissions(supplier: str) -> dict:
    """Returns the scope 1, scope 2 emissions and water usage of a specified supplier using supplier id.
    Args:
        supplier (str)  : The id of the supplier for whom to retrieve the esg score.
    Returns:
        dict: status and result or error msg.
    """
    filename = 'supplier_emissions.csv'    
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
            
                reader = csv.DictReader(file)  # Reads the file as a dictionary
            
                for row in reader:
                    if row["supplier_id"] == supplier:
                        
                        return {"status": "success",  "supplier": supplier, "Scope 1 Emissions": row["Scope1_emissions"], "Scope 2 Emissions": row["Scope2_emissions"], "Water USage": row["Water_Usage_m3"],"last_updated": row["Reporting Year"]}
                    
                    
        except Exception as e:
           return {"status": "error", "Exception": e}


#Fetch function to get the normalized esg score of a supplier
def get_esg_score(supplier: str) ->dict:
    """Returns the esg score of a specified supplier using supplier esg data file.
    Args:
        supplier (str)  : The id of the supplier for whom to retrieve the esg score.
    Returns:
        dict: status and result or error msg.
    """
    filename = 'suppliers_esg_data.csv'
    
    #file_path = f"gs://{bucket_name}/{folder_path}/{filename}"
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
            
                reader = csv.DictReader(file)  # Reads the file as a dictionary
            
                for row in reader:
                    if row["Supplier Id"] == supplier:
                    
                        if row["Provider"] == "EcoVadis":
                            esg_score = row["Overall score"]
                        elif row["Provider"] == "Sustainalytics":
                            esg_score = max(0, 100-row["Risk Score"])
                        elif row["Provider"] == "MSCI":
                            esg_score = lambda grade:{
                                    "AAA":100,"AA": 90, "A": 80,
                                    "BBB":70, "BB":60, "B":40,
                                    "CCC":20
                                }.get(grade.upper(), 0)(row["Rating"])
                        else:
                            esg_score = None
                        if esg_score is not None:
                            
                            return {"status": "success", "provider": row["Provider"], "supplier": supplier, "esg_score": esg_score, "last_updated": row["Reporting Year"]}
                        else:
                            return {"status": f"Failed processing for {supplier}"}
                    
           
        except Exception as e:
            return {"status": "error", "Exception": e}

#Fetch function to get the supplier audit score
def get_supplier_auditscore(supplier: str) -> dict:
    """Returns the audit score of a specified supplier.
    Args:
        supplier (str)  : The id of the supplier for whom to fetch the audit data.
    Returns:
        dict: status and result or error msg.
    """
    filename = 'supplier_audits.csv'    
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
            
                reader = csv.DictReader(file)  # Reads the file as a dictionary
            
                for row in reader:
                    if row["supplier_id"] == supplier:
                        return {"status": "success",  "supplier": supplier, "Audit Score": row["score"]}
                                     
            
        except Exception as e:
            return {"status": "error", "Exception": e}

#Fetch function to predict the risk factor of a supplier
def predict_supplier_risk(supplier: str) ->dict:
    """Returns the risk factor of a specified supplier based on ESG and operational data.
    Args:
        supplier (str)  : The id of the supplier for which to predict the risk based on ESG and operational data.
    Returns:
        dict: status and result or error msg.
    """
    try:
        return {"status": "success", "supplier": {supplier},"risk factor": "High"}
    except:
        return {"status": "error"}  


root_agent = Agent(
    name="sustainable_procurement_Agent",
    model=model_name,
    description="Evaluates and scores suppliers based on emissions, labor ethics, certifications and other sustainability factors.",
    instruction="""
    You are a sustainability procurement SME.
    Your goal is to promote sourcing from environmentally and socially responsible suppliers
    You have capabilities to score suppliers, detect supplier risks and recommend alternative suppliers
    You will be provided an input of the material or product to be sourced either with no location specifics or with some location specifics
    You are provided with a tool to get the list of vendors for the material or product to be sourced. If no location provided, keep it empty
    For each of the suppliers in the list
        - always use get_esg_score tool to fetch supplier environment scores
        - always use get_supplier_emissions tool to fetch supplier emissions data
        - always use get_supplier_auditscore tool to fetch supplier social audit data
        
  
    Ensure that all the scores and certification data is recent, within 2 years
    Normalize the various scores for a supplier with the following weights
        - 50% weight to overall ESG score, a higher score indicates a sustainable supplier
        - 15% to emissions and water usage data, low emissions and low water usage is a sustainable supplier
        - 15% to certification data, if available, valid certification indicates a sustainable supplier
        - 20% to supplier audit score, higher score is a sustainable supplier
    Compare and rank the suppliers based on the above normalization with a scorecard listing the supplier and its normalized sustainability score only
    If asked to recommend suppliers near a location, use your knowledge base to determine from the ranked supplier list which suppliers with regions adjacent to the specified location
    If any tool returns an error, inform the user politely
    If the tools are successful, present the results to the user
    """,
   # output_key = "SustainableSuppliers",
    #before_model_callback=log_query_to_model,
    after_model_callback=log_model_response,
    # Add the function tools below
    tools=[get_vendor_list,get_esg_score, get_supplier_emissions,get_supplier_auditscore]
       
)



