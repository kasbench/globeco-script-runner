import logging
import sys
import importlib
import requests
import json
import datetime
import csv
import uuid
import random


def main():
    if len(sys.argv) < 2:
        print("Usage: python runner.py <script> [args...]")
        sys.exit(1)

def configure_logging():
    """
    Configure logging for the application.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


def get_current_time():
    """
    Get the current time in the desired format.
    """ 
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def is_success(status_code):
    return status_code >= 200 and status_code < 300

def get_pricing_tickers(url='http://globeco-pricing-service:8083/api/v1'):
    response = requests.get(url + "/prices")
    if is_success(response.status_code):
        data = response.json()  # If the response is JSON
        return [d['ticker'] for d in data]
    else:
        print(f"Error: {response.status_code}")

def get_security_names(tickers):
    security_names = {ticker: ticker for ticker in tickers}
    with open('./files/tickers.json') as sec_file:
        sec_raw = json.load(sec_file)
        sec = {s['ticker']: s['title'] for s in sec_raw.values() }
        for key, value in security_names.items():
            if key == value and sec.get(key):
                security_names[key] = sec[key]
    return security_names

def get_or_create_security_type(sec_type='CS', url='http://globeco-security-service:8000/api/v1'):
    response = requests.get(url + "/securityTypes")
    if is_success(response.status_code):
        data = response.json() 
        for d in data:
            if d['abbreviation'] == 'sec_id':
                return d['securityTypeId']
    else:
        print(f"Error: {response.status_code}")
        return

    payload = {'abbreviation': 'CS', 'description': 'Common Stock', 'version': 1 }
    headers = {'Content-Type': 'application/json'}
    
    response = requests.post(url + "/securityTypes", headers=headers, json=payload)
    if is_success(response.status_code):
        data = response.json()  # If the response is JSON
        return data['securityTypeId']
    else:
        print(f"Error: {response.status_code}")
    

def get_or_create_security(ticker, name, security_type, url='http://globeco-security-service:8000/api/v1'):
    response = requests.get(url + "/securities")
    if is_success(response.status_code):
        data = response.json()  
        for d in data:
            if d['ticker'] == ticker:
                return d['securityId']
    else:
        print(f"Error (GET): {response.status_code}")
        return
    
    payload = {"ticker": ticker, "description": name, "securityTypeId": security_type, "version": 1 }
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url + "/securities", headers=headers, json=payload)
    if is_success(response.status_code):
        data = response.json() 
        return data['securityId']
    else:
        print(f"Error (POST): {response.status_code}, {response.reason}")


def create_securities_if_not_exist(pricing_url='http://globeco-pricing-service:8083/api/v1', security_url='http://globeco-security-service:8000/api/v1'):
    tickers = get_pricing_tickers(pricing_url)
    security_names = get_security_names(tickers)
    security_type_id = get_or_create_security_type('CS',url=security_url)
    securities = {}
    for ticker in tickers:
        name = security_names[ticker]
        security_id = get_or_create_security(ticker, name, security_type_id, url=security_url)    
        securities[ticker] = {'name': name, 'security_id': security_id, 'security_type_id': security_type_id}

    return securities


def get_or_create_portfolio(name, url='http://globeco-portfolio-service:8000/api/v1'):
    response = requests.get(url + "/portfolios")
    if is_success(response.status_code):
        data = response.json() 
        for d in data:
            if d['name'] == name:
                return d['portfolioId']
    else:
        print(f"Error (GET): {response.status_code}")

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    formatted_date_time = now_utc.isoformat().replace('+00:00', 'Z')

    payload = {"name": name, "dateCreated": formatted_date_time, "version": 1 }
    headers = {'Content-Type': 'application/json'}
    
    response = requests.post(url + "/portfolios", headers=headers, json=payload)
    if is_success(response.status_code):
        data = response.json() 
        return data['portfolioId']
    else:
        print(f"Error (POST): {response.status_code}, {response.reason}")

def get_portfolios(url='http://globeco-portfolio-service:8000/api/v1'):
    response = requests.get(url + "/portfolios")
    if is_success(response.status_code):
        data = response.json() 
        return data
    else:
        print(f"Error (GET): {response.status_code}")
        

def create_portfolio(name, url='http://globeco-portfolio-service:8000/api/v1'):
    
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    formatted_date_time = now_utc.isoformat().replace('+00:00', 'Z')

    payload = {"name": name, "dateCreated": formatted_date_time, "version": 1 }
    headers = {'Content-Type': 'application/json'}
    
    response = requests.post(url + "/portfolios", headers=headers, json=payload)
    if is_success(response.status_code):
        data = response.json() 
        return data['portfolioId']
    else:
        print(f"Error (POST): {response.status_code}, {response.reason}")

def get_or_create_all_portfolios(n, url='http://globeco-portfolio-service:8000/api/v1'):
    names = {p['name']: p['portfolioId'] for p in get_portfolios(url=url)}
    portfolios = {}
    for i in range(n):
        name = f'Portfolio {i}'
        if names.get(name):
            portfolios[i] = {'name': name, 'portfolio_id': names[name]}
        else:
            portfolio_id = create_portfolio(name)
            portfolios[i] = {'name': name, 'portfolio_id': portfolio_id}

    return portfolios


def post_transactions(transactions, max_post=50, url='http://globeco-portfolio-accounting-service:8087/api/v1'):

    pos = 0
    results = []
    transactions_len = len(transactions)
    total_requested = successful = failed = 0
    while True:
        if transactions_len == 0:
            return total_requested, successful, failed, results
        if pos >= transactions_len:
            return total_requested, successful, failed, results
        next_pos = pos + max_post                   
        if next_pos > transactions_len:
            sub_transactions = transactions[pos:]
        else:
            sub_transactions = transactions[pos:next_pos]
        pos += max_post
        # results.append(sub_transactions)
        
        
        # payload = {"name": name, "dateCreated": formatted_date_time, "version": 1 }
        headers = {'Content-Type': 'application/json'}

        # print('Posting: ', [json.dumps(s) for s in sub_transactions])
        
        response = requests.post(url + "/transactions", headers=headers, json=sub_transactions)
        if is_success(response.status_code):
            data = response.json() 
            # print("data: ", data)
            summary = data['summary']
            total_requested += summary['totalRequested']
            successful += summary['successful']
            failed += summary['failed']
            results.append(data)
        else:
            print(f"Error (POST): {response.status_code}, {response.reason}")

    

def create_cash_transactions(portfolios):
    # 60% of portfolios between $100,000 and $1 million.  The rest between $1 million and $4 million.
    transactions = []
    today = datetime.date.today()
    today_formatted = today.strftime("%Y%m%d")
    for portfolio in portfolios[:]:
        if random.random() < 0.6:
            cash = random.randrange(100_000, 1_000_000)
        else:
            cash = random.randrange(1_000_000, 4_000_000)

        transaction = { 
            'portfolioId' : portfolio,
            'price': 1,
            'quantity': cash,
            # 'securityId': '683b6b9620f302c879a5fef4',
            'sourceId': str(uuid.uuid4()),
            'transactionDate': today_formatted,
            'transactionType': 'DEP' }
        transactions.append(transaction)

    return transactions


def create_security_transaction(portfolio_id, security_id, quantity, price, transaction_date, source_id, transaction_type):
    # 60% of portfolios between $100,000 and $1 million.  The rest between $1 million and $4 million.
    transactions = []
    today = datetime.date.today()
    today_formatted = today.strftime("%Y%m%d")
    transaction = { 
        'portfolioId' : portfolio_id,
        'price': price,
        'quantity': quantity,
        'securityId': security_id,
        'sourceId': str(uuid.uuid4()),
        'transactionDate': today_formatted,
        'transactionType': transaction_type }
    transactions.append(transaction)

    return transactions

def get_securities(url='http://globeco-security-service:8000/api/v1'):
    response = requests.get(url + "/securities")
    if is_success(response.status_code):
        return response.json()  
    
    print(f"Error (GET): {response.status_code}")
    return

def generate_model_positions(num_positions, securities, cash=0.05, increment=0.005):
    model_securities = random.sample(securities, num_positions)
    security_allocation = 1.0 - cash
    while True:
        positions  = {security['securityId']: 0 for security in model_securities}
        overweighted_20_percent = int(num_positions * 0.2)
        weights = [1 for _ in range(num_positions - overweighted_20_percent)] + [2 for _ in range(overweighted_20_percent)]
        sum_of_targets = 0.0
        while sum_of_targets < security_allocation:
            security = random.choices(model_securities, weights=weights,k=1)[0]
            positions[security['securityId']] += increment
            sum_of_targets += increment
        if round(min(positions.values()),3) > 0:
            break    
        # print("Try again")
    
    return {k: round(v,3) for k,v in positions.items()}

def post_model(name, positions, portfolios, url='http://globeco-order-generation-service:8088/api/v1'):
    positions = [{'security_id': k, 'target': v, 'high_drift': 0.005, 'low_drift': 0.005} for k,v in positions.items()]
    payload = {
        "name": name,
        "positions": positions,
        "portfolios": portfolios}
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url + "/models", headers=headers, json=payload)
    if is_success(response.status_code):
        return response.json()
    else:
        print(f"Error (POST): {response.status_code}, {response.reason}")
        return

def split_portfolios_randomly(portfolios, num_portfolios_per_model):
    """
    Split portfolios into smaller lists of at most num_portfolios_per_model.
    Each portfolio appears in exactly one list.
    """
    # Shuffle the portfolios randomly
    shuffled_portfolios = portfolios.copy()
    random.shuffle(shuffled_portfolios)
    
    # Split into chunks
    portfolio_groups = []
    for i in range(0, len(shuffled_portfolios), num_portfolios_per_model):
        group = shuffled_portfolios[i:i + num_portfolios_per_model]
        portfolio_groups.append(group)
    
    return portfolio_groups

def create_models(num_positions_per_model, num_portfolios_per_model, num_models = None,  url='http://globeco-order-generation-service:8088/api/v1'):
    securities = get_securities()
    portfolios = get_portfolios()
    portfolios = [p['portfolioId'] for p in portfolios]
    if num_models is None:
        num_models = len(portfolios) // num_portfolios_per_model
        print(f"Number of models: {num_models}")
    # Split portfolios into smaller random groups
    portfolio_groups = split_portfolios_randomly(portfolios, num_portfolios_per_model)
    
    for i in range(num_models):
        positions = generate_model_positions(num_positions_per_model, securities)
        # Use the i-th portfolio group, cycling through if we have more models than groups
        portfolio_group = portfolio_groups[i % len(portfolio_groups)]
        post_model(f"Model {i}", positions, portfolio_group, url)                    



def run(*args, **kwargs):
    """
    Placeholder for the initialize script logic.
    """
    security_service_url = 'http://globeco-security-service:8000/api/v1' 
    portfolio_service_url = 'http://globeco-portfolio-service:8000/api/v1' 
    order_service_url = 'http://globeco-order-service:8081/api/v1'
    trade_service_url = 'http://globeco-trade-service:8082/api/v1'
    execution_service_url = 'http://globeco-execution-service:8084/api/v1'
    portfolio_accounting_service_url = 'http://globeco-portfolio-accounting-service:8087/api/v1'
    pricing_service_url = 'http://globeco-pricing-service:8083/api/v1' 
    order_generation_service_url = 'http://globeco-order-generation-service:8088/api/v1'
    
    # Configure logging
    logger = configure_logging()

    logger.info("Starting the initialize script")

    securities = create_securities_if_not_exist(pricing_url=pricing_service_url, security_url=security_service_url)  

    logger.info("Securities created: %s", len(securities))

    # portfolios = get_or_create_all_portfolios(10_000, url=portfolio_service_url)

    # logger.info("Portfolios created: %s", len(portfolios))  

    # portfolio_ids = [p['portfolio_id'] for p in portfolios.values()]

    # transactions = create_cash_transactions(portfolio_ids[:])

    # total_requested, successful, failed, results = post_transactions(transactions, url=portfolio_accounting_service_url)

    # logger.info("Transactions posted: %s", total_requested)
    # logger.info("Transactions successful: %s", successful)
    # logger.info("Transactions failed: %s", failed)

    # create_models(num_positions_per_model=50, num_portfolios_per_model=100, url=order_generation_service_url)

    # logger.info("Models created")

    logger.info("Script completed")


