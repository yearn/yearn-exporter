import logging
import requests


logger = logging.getLogger(__name__)

def gql_post(endpoint, vars, query):
    gql = query
    for key in vars:
        value = vars[key]
        if isinstance(value, str): value = '"' + value + '"'
        else: value = str(value)
        gql = gql.replace("$" + key, value)

    logger.info(gql)
    response = requests.post(url=endpoint, json={'query': gql})
    if response.status_code == 200:
        return response.json()
    else:
        raise RuntimeError(f'response.status_code {response.status_code}')
