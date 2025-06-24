import logging
import google.cloud.logging
 
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse, LlmRequest
import requests
 
# Global variable to store token count
total_token_count = 0
#function to compute the environmental impact of each query made to the solution
def fetch_impact_AI(input_data):
    try:
        url = "https://ecoai-ghg7gxd6c7bhhweg.eastus-01.azurewebsites.net/api/v1/GenAICCV1"
        params = {
            'AIServiceProvider':{input_data['aiServiceProvider']},
            'LLM':{input_data['llm']},
            'AvgNoOfTokensPerQuery':{input_data['avgTokens']},
            'NoOfQueries':{input_data['queries']},
            'region':{input_data['region']}
        }
        headers = {
            'API_KEY': '-FGOI476eyPBLKsbPXwnfaL3F0M2FdVx7OqPFl1ZcdA', 
            'email': 'sunitha.kaslay@capgemini.com',
            'Content-Type': 'application/json'
        }
        print(f"params:{params}")
        response = requests.get(url,headers=headers,params=params,data='')
               
        if response.status_code != 200:
            return{"status": "error", "message": response.status_code + " " + response.message}

        data = response.json()       
        return {"status": "success", "data": data}
    except Exception as error:
        return{"status": "error", "message": "error fetching emissions data"}
    

def log_query_to_model(callback_context: CallbackContext, llm_request: LlmRequest):
    cloud_logging_client = google.cloud.logging.Client()
    cloud_logging_client.setup_logging()
    if llm_request.contents and llm_request.contents[-1].role == 'user':
         if llm_request.contents[-1].parts and "text" in llm_request.contents[-1].parts:
            last_user_message = llm_request.contents[-1].parts[0].text
            logging.info(f"[query to {callback_context.agent_name}]: " + last_user_message)
 
def log_model_response(callback_context: CallbackContext, llm_response: LlmResponse):
    cloud_logging_client = google.cloud.logging.Client()
    cloud_logging_client.setup_logging()
    if llm_response.content and llm_response.content.parts:
        for part in llm_response.content.parts:
            if part.text:
                logging.info(f"[response from {callback_context.agent_name}]: " + part.text)
                #logging.info(f"[response from {callback_context.agent_name}]:")
            elif part.function_call:
                #logging.info(f"[function call from {callback_context.agent_name}]: " + part.function_call.name)
                logging.info(f"[function call from {callback_context.agent_name}]: " )
 
    
    usage = getattr(llm_response, "usage_metadata", None)
    if usage:
        total_token_count = getattr(usage, "total_token_count", 0) or 0
        logging.info(f"Usage Impact of {callback_context.agent_name}: {total_token_count} tokens")
        #function call to log impact of using the solution
        input_data = {
                'aiServiceProvider': 'Google',
                'llm': 'PaLM 2',
                'avgTokens': total_token_count,
                'queries': 1,
                'region': 'United States'
            }
        result=fetch_impact_AI(input_data)
        if result['status'] == 'success':
            logging.info(f"Result: {result['data']}")
        else:
            logging.info(f"Error: {result['message']} ")
       
    else:
        logging.info("[Token Usage] No usage metadata found.")