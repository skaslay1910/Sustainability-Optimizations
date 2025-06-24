import os
import sys
import asyncio

import csv
from dotenv import load_dotenv
from google.adk.agents import Agent

from google.cloud import storage
from google.adk.sessions import InMemorySessionService
from google.genai import types
from typing import Optional, List, Dict
from google.adk.tools.tool_context import ToolContext
from Smart_Waste_Inventory.agent import root_agent as Smart_Waste_Inventory_Agent
from Sustainable_Procurement.agent import root_agent as sustainable_procurement_Agent 
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

# stores conversation history & state

# session_service_stateful= InMemorySessionService()
# user_id_stateful = "user_state_demo"
# session_id_stateful = "session_state_demo"
# async def create_session():
#    session = await session_service_stateful.create_session(
#         app_name = "Sustainability Optimizations",
#         user_id = user_id_stateful,
#         session_id = session_id_stateful,
#         state = {"totaltokencount": 0, "SustainableSuppliers": None, "WasteRiskScore": None}     
#     )
   
# #asyncio.run(create_session())
# create_session()
#print(f"Session created: App = 'Sustainability Optimizations', User = '{user_id_stateful}', Session = '{session_id_stateful}'")
# Tool: Get Supplier Product Purchase Data
def get_supplier_product_purchase_data(supplier_id: str, product_id: str) -> dict:
    """Fetch purchase data for a given supplier or product
    Args:
        supplier_id (str): The id of the supplier for which to retrieve the purchase data.
        product_id (str): The id of the product for which to retrieve the purchase
    Returns:
        dict: status and result or error msg.
    """
    filename = "supplier_product_purchase_data.csv"
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
                if supplier_id:
                    return {"status": "success", "records": [row for row in reader if row["supplier_id"] == supplier_id]}
                elif product_id:
                    return {"status": "success", "records": [row for row in reader if row["product_id"] == product_id]}
                else:
                    return {"status": "error", "message": "Both supplier_id and product_id are missing."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

#Agent Definition
root_agent = Agent(
    name="Orchestration_Agent",
    model=model_name,
 
    description="Coordinate across all sustainability agents to balance tradeoffs and optimize for both sustainability and business performance.",
    instruction="""
    You are an orchestration agent responsible for analyzing user prompts and delegating them to the appropriate agent based on the intent of the prompt.
    You will be provided with a user prompt and a list of available agents with their corresponding tasks or areas of expertise. Your task is to analyze the user prompt and determine which agent is best suited to handle the task.
    You also perform tradeoff optimization across sustainability metrics and business KPIs
    
    Follow these steps:
    1. Analyze the user prompt and identify the key intent or task being requested. 
    2. For a greeting, respond politely stating your key role.
    3. Review the list of available agents and their descriptions to determine which agent's expertise aligns best with the user's intent.
    4. If there is a clear match between the user's intent and an agent's expertise, select that agent.
        Output your response in the following format:
        **Selected Agent:** [Name of the selected agent]
        **Reason:** [Brief explanation of why this agent was chosen]

        Example:
        **User Prompt:** "Forecast waste risk for a product"
        **Available Agents:**
        - Smart_Waste_Agent: Specializes in waste management and risk assessment.
        - Sustainable_Procurement_Agent: Focuses on sustainable sourcing and procurement practices.

        **Output:**
        **Selected Agent:** Smart_Waste_Agent
        **Reason:** The user prompt is related to waste risk assessment, which falls under the expertise of the Smart_Waste_Agent.

    5. If the user prompt is unclear or does not match any of the available agents, respond with an error message indicating that the prompt cannot be classified.
    6. Once the subagent completes its response, get the control back to you, so that every subsequent prompt travels through you
    7. If the user prompt is to make an optimal tradeoff/balance between suppliers and operational efficiency
       - Use your knowledge base to determine geographical location, distance, lead times etc 
       - Search the sub-agent's response data from the session state to look at all scores generated
       - Example:
            **User Prompt:** "Recommend sustainable suppliers without delaying operations"
            - Optimize tradeoff based on sustainability score of the suppliers and shorter lead times. Choose suppliers from neighbouring areas but with better Sustainability scores
              
    If any tool returns an error, inform the user politely
    If the tools are successful, present the results to the user
    """,
    
    #before_model_callback=log_query_to_model,
    after_model_callback=log_model_response,
    # Add the function tools below
    tools=[get_supplier_product_purchase_data],
     # Add the sub_agents parameter when instructed below this line
    sub_agents = [sustainable_procurement_Agent, Smart_Waste_Inventory_Agent]
   
)
 




