import asyncio
import concurrent.futures
import json
from pprint import pprint

import requests
import os
import sys
import falcon
from pymemcache.client import base

from apscheduler.schedulers.background import BackgroundScheduler
from functools import partial

mc = base.Client(('memcached', 11211))

tokens = []

# Load Environmental Variables

max_workers = int(os.environ['GET_UPSTREAM_BALANCES_WORKERS'])

cacheExpirationTime = int(os.environ['CACHE_EXPIRATION_TIME'])

upstream = os.environ['UPSTREAM_API']

def get_tokens():
    global tokens
    temp = []
    with open("all_tokens.json", "r") as read_file:
        data = json.load(read_file)
    for token in data:
        if token['symbol'] == 'EOS' and token['account'] == 'eosio.token':
            temp.append((token['symbol'], token['account']))
        elif token['symbol'] == 'EOS':
            pass
        else:
            temp.append((token['symbol'], token['account']))
    tokens = temp




async def get_balances(account, targetTokens):
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        loop = asyncio.get_event_loop()
        futures = []
        mapping = {}
        # Create a future execution of the post request in the futures pool
        for (symbol, code) in targetTokens:
            mapping[symbol] = code
            futures.append(
                loop.run_in_executor(
                    pool,
                    partial(
                        requests.post,
                        upstream + '/v1/chain/get_currency_balance',
                        json={
                            "account": account,
                            "code": code,
                            "symbol": symbol
                        }
                    )
                )
            )
        balances = []
        # Await for all processes to complete
        for r in await asyncio.gather(*futures):
            if r.status_code == 200:
                for token in r.json():
                    amount, symbol = token.split(' ')
                    balances.append({
                        'amount': amount,
                        'code': mapping[symbol],
                        'symbol': symbol,
                    })


        #caching balances
        mc.set(account, balances, cacheExpirationTime)
        # Return balances
        return balances

class GetCurrencyBalances:
    def on_post(self, req, resp):
        # Process the request to retrieve the account name
        request = json.loads(req.stream.read())
        pprint(request)
        # Establish session for retrieval of all balances
        with requests.Session() as session:
            balances = []
            # Determine which tokens to load
            targetTokens = tokens
            # If a tokens array is specified in the request, use it
            if 'tokens' in request:
                targetTokens = []
                for token in request.get('tokens'):
                    contract, symbol = token.split(':')
                    targetTokens.append((symbol, contract))

            account = request.get('account')
            balances = mc.get(account)

            if not balances:
                # Launch async event loop to gather balances
                loop = asyncio.get_event_loop()
                balances = loop.run_until_complete(get_balances(account, targetTokens))
            else:
                balances = balances.decode('UTF-8')
            # Server the response
            resp.body = json.dumps(balances)

# Load the initial tokens on startup
get_tokens()

# Schedule tokens to be refreshed from smart contract every minute
scheduler = BackgroundScheduler()
scheduler.add_job(get_tokens, 'interval', minutes=1, id='get_tokens')
scheduler.start()

# Launch falcon API
app = falcon.API()
app.add_route('/v1/chain/get_currency_balances', GetCurrencyBalances())
