import RPi.GPIO as gpio
import threading
import firebase_admin
import time
import datetime
import requests
import json
# import spidev
from firebase_admin import credentials
from firebase_admin import firestore

# spi = spidev.SpiDev()
# spi.open(0, 0)

# connect to firebase
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


def get_group_token(floor, tokens):
    if (len(tokens) != 0):
        print(len(tokens))
        token_name = "floor_" + str(floor)
        payload = json.dumps({
           "operation": "create",
           "notification_key_name": token_name,
           "registration_ids": tokens,
            })
        response = requests.request("POST", url_group , headers=headers_group, data=payload)
        print(token_name)
        print(json.loads(response.text))
        try:
            return(json.loads(response.text)['notification_key'])
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
    response = requests.request("POST", url_group , headers=headers_group, data=payload)
    print(token_name)
    print(json.loads(response.text))

class FlameSensor:
    def __init__(self, pin):
        self.pin = pin
        gpio.setmode(gpio.BCM)
        gpio.setup(self.pin, gpio.IN, pull_up_down=gpio.PUD_UP)


"""
class MQ2Sensor:
    def __init__(self, ch_num):
        self.chNum = ch_num

    def read_adc(self):
        if self.chNum > 7 or self.chNum < 0:
            return -1
        buff = spi.xfer2([6 | (self.chNum & 4) >> 2, (self.chNum & 3) << 6, 0])
        adc_value = ((buff[1] & 15) << 8) + buff[2]
        return adc_value

    def gas(self):
        mq2 = self.read_adc()
        print(f"gas : {mq2}")
        return mq2
"""


def calc_time(self):
    now = datetime.datetime.now()
    date = now.strftime("%Y/%m/%d %H:%M")
    return date


class Floor:
    def __init__(self, floor: int, flame_pin: int, ch_num: int):
        self.floor = floor
        self.is_first = True
        # self.mq2Sensor = MQ2Sensor(ch_num)
        self.flameSensor = FlameSensor(flame_pin)
        self.gasStandard = 200  # 가스 센서 통해 실험 해보고 값 변경할 것.

    def send_message_to_firebase(self):
        date = calc_time()

        # if self.mq2Sensor.gas() > self.gasStandard:

        print(f'Fire detected on {self.floor} floor')
        send_fcm(self.floor, is_first)
        doc_ref.set({
                u'Time': date,
                u'Floor': self.floor,
                u'FireDetected': u'TRUE'
        })
        if (self.is_first):
            self.is_first == False

    def fire_detect(self):
        gpio.add_event_detect(self.flameSensor.pin, gpio.RISING, callback=lambda x: self.send_message_to_firebase(),
                              bouncetime=50)


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


def send_fcm(fire_floor, is_first):
    users_ref = db.collection(u'workplace')
    docs = users_ref.stream()
    for floor in range(1,3):
        group_key = get_group_token(floor, floors_dict[floor])
        print(f'send to {group_key}')
        # print((doc.to_dict()))
        if (group_key != 0):
            payload = json.dumps({
                "to": group_key,
                "data": {
                    "floor": floor,
                    "fire_floor" : fire_floor,
                    "floor_1_people" : len(floors_dict[1]),
                    "floor_2_people" : len(floors_dict[2])
                }
            })
            response = requests.request("POST", url, headers=headers, data=payload)
            print(response.text)
            remove_group_token(floor, floors_dict[2], group_key)



# Create a callback on_snapshot function to capture changes

def on_snapshot(col_snapshot,changes, read_time):
    print(u'Callback received query snapshot.')
    # print(f"floor :")
    for doc in col_snapshot:
        if ((doc.to_dict())['enter'] == True):
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


First_floor = Floor(1, 17, 0)
Second_floor = Floor(2, 22, 1)
# Third_floor = Detect.Floor(3, 27, 2)


def process():
    First_floor.fire_detect()
    Second_floor.fire_detect()
    # Third_floor.fire_detect()
    while True:
        time.sleep(3)


if __name__ == '__main__':
    try:
        print("Detect Start")
        process()
        start_watch()
    except KeyboardInterrupt:
        print()
        print("End by KeyboardInterrupt!")
        gpio.cleanup()
