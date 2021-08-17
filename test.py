import threading
import firebase_admin
import time
import datetime
import requests
import json
# import spidev
from firebase_admin import credentials
from firebase_admin import firestore

cred = credentials.Certificate("beacon-client-app-firebase-adminsdk-52b5p-186f3fb413.json") #key file name
firebase_admin.initialize_app(cred)

db = firestore.client()
doc_ref = db.collection(u'FireState').document(u'Sensors')

# preprocess to send push message
url = "https://fcm.googleapis.com/fcm/send"
url_group = "https://fcm.googleapis.com/fcm/notification"

headers = {
  'Authorization': 'key=AAAAFYmlCLM:APA91bFMWQ1z8LQvRn_ffgxx9_CsOwAj4uVhINfwEDxIRdbE254cPkPvjuC3Dxt4adtfEzaVUbIUEAmIjZR7A_dBh2reGklHoZhlcsSSRWeodwBndLjXyxwOpADWI9oIH9CkEpe-Frq2', # key value of firebase project
  'Content-Type': 'application/json'
}

headers_group = {
  'Authorization': 'key=AAAAFYmlCLM:APA91bFMWQ1z8LQvRn_ffgxx9_CsOwAj4uVhINfwEDxIRdbE254cPkPvjuC3Dxt4adtfEzaVUbIUEAmIjZR7A_dBh2reGklHoZhlcsSSRWeodwBndLjXyxwOpADWI9oIH9CkEpe-Frq2', # key value of firebase project
  'Content-Type': 'application/json',
  'project_id' : '92503607475'
}
callback_done = threading.Event()

floors_dict = {1: [], 2: []}


img_url = ['https://firebasestorage.googleapis.com/v0/b/beacon-client-app.appspot.com/o/evacuation_1.png?alt=media&token=2dafbbfd-96dd-4b8a-b620-3df0d875f696',
    'https://firebasestorage.googleapis.com/v0/b/beacon-client-app.appspot.com/o/evacuation_2.png?alt=media&token=f8d942f7-d5d2-4e10-89f0-07d50bad7f12']


def get_group_token(floor, tokens):
    if len(tokens) != 0:
        print(len(tokens))
        token_name = "floor_" + str(floor)
        payload = json.dumps({
           "operation": "create",
           "notification_key_name": token_name,
           "registration_ids": tokens,
            })
        response = requests.request("POST", url_group, headers=headers_group, data=payload)
        print(token_name)
        print(json.loads(response.text))
        try:
            return json.loads(response.text)['notification_key']
        except:
            return 0
    else:
        return 0


def remove_group_token(floor, tokens, not_key):
    token_name = "floor_" + str(floor)
    payload = json.dumps({
       "operation": "remove",
       "notification_key_name": token_name,
       "registration_ids": tokens,
       "notification_key" : not_key
        })
    response = requests.request("POST", url_group, headers=headers_group, data=payload)
    print(token_name)
    print(json.loads(response.text))

def send_fcm(fire_floor):
    users_ref = db.collection(u'workplace')
    docs = users_ref.stream()
    for floor in range(1, 3):
        group_key = get_group_token(floor, floors_dict[floor])
        print(f'send to {group_key}')
        # print((doc.to_dict()))
        if group_key != 0:
            payload = json.dumps({
                "to": group_key,
                "data": {
                    "floor": floor,
                    "fire_floor": fire_floor,
                    "floor_1_people": len(floors_dict[1]),
                    "floor_2_people": len(floors_dict[2]),
                    "image": img_url[floor -1]
                }
            })
            response = requests.request("POST", url, headers=headers, data=payload)
            print(response.text)
            remove_group_token(floor, floors_dict[floor], group_key)



def on_snapshot(col_snapshot, changes, read_time):
    print(u'Callback received query snapshot.')
    # print(f"floor :")
    for doc in col_snapshot:
        if (doc.to_dict())['enter']:
            add_dict(doc.id, (doc.to_dict())['floor'])
    callback_done.set()


def start_watch():
    for i in range(1, 3):
        col_query = db.collection(u'workplace').where(u'floor', u'==', i)
        query_watch = col_query.on_snapshot(on_snapshot)
        time.sleep(3)
        db.collection(u'floors').document(str(i)).set({
            'tokens': floors_dict[i]
        })


def add_dict(to_add, floor):
    for num, floors in floors_dict.items():
        if num != floor and to_add in floors:
            floors.remove(to_add)
            floors_dict[num] = floors
        elif num == floor and to_add not in floors:
            floors_dict[floor].append(to_add)
        db.collection(u'floors').document(str(num)).set({
            'tokens': floors_dict[num]
        })

if __name__ == '__main__':
    try:
        print("Detect Start")
        start_watch()
        while(1):
            fire_floor = int(input())
            if(fire_floor > 0):
                send_fcm(fire_floor)
            else:
                break
    except KeyboardInterrupt:
        print()
        print("End by KeyboardInterrupt!")
        gpio.cleanup()
