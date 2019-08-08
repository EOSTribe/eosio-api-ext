import json
import requests
import os
import falcon

# Load Environmental Variables
full_api = os.environ.get('GET_ACTIONS_ENDPOINT', "https://eos.greymass.com")

class GetActions:
    def on_post(self, req, resp):
        position = -1
        offset = -500
        request = json.loads(req.stream.read())
        # Retrieve Variables
        account_name = request.get('account_name')
        # offset = int(request.get('offset'))
        # position = int(request.get('pos'))
        # Form the default endpoint path
        endpoint = full_api + '/v1/history/get_actions'
        # Determine if this query fits in the limit history dataset
        # Create Request
        r = requests.post(endpoint, json={
            "account_name": account_name,
            "pos": position,
            "offset": offset
        })
        jsonResponse = json.loads(r.text)
        actions = jsonResponse['actions']
        actionsTransfer = []
        for action in actions:
            if action['action_trace']['act']['name'] == "transfer":
                temp = {}
                temp['action'] = {}
                temp['action']['act'] = {}
                temp['action']['act']['data'] = action['action_trace']['act']['data']
                actionsTransfer.append(temp)


        response = {"actions": actionsTransfer}
        # Return response
        resp.body = json.dumps(response,ensure_ascii=False)

# Launch falcon API
app = falcon.API()
app.add_route('/v1/history/get_actions', GetActions())
app.add_route('/v2/history/get_actions', GetActions())

