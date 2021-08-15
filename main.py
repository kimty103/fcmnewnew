import RPi.GPIO as gpio
import spidev as spi
import threading
import firebase_admin
import time
from firebase_admin import credentials
from firebase_admin import firestore

#connect to firebase database

spi = spi.SpiDev()
spi.open(0, 0)

cred = credentials.Certificate("beacon-client-app-firebase-adminsdk-52b5p-186f3fb413.json") #key file name
firebase_admin.initialize_app(cred)

db = firestore.client()
doc_ref = db.collection(u'FireState').document(u'Sensors')

#preprocess to send push message
url = "https://fcm.googleapis.com/fcm/send"
headers = {
  'Authorization': 'key=AAAAFYmlCLM:APA91bFMWQ1z8LQvRn_ffgxx9_CsOwAj4uVhINfwEDxIRdbE254cPkPvjuC3Dxt4adtfEzaVUbIUEAmIjZR7A_dBh2reGklHoZhlcsSSRWeodwBndLjXyxwOpADWI9oIH9CkEpe-Frq2', # key value of firebase project
  'Content-Type': 'application/json'
}

callback_done = threading.Event()

floors_dict = { 1:[], 2:[]}


class FlameSensor:
    def __init__(self, pin):
        self.pin = pin
        gpio.setmode(gpio.BCM)
        gpio.setup(self.pin, gpio.IN, pull_up_down=gpio.PUD_UP)


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


class Floor:
    def __init__(self, floor: int, flame_pin: int, ch_num: int):
        self.floor = floor
        self.mq2Sensor = MQ2Sensor(ch_num)
        self.flameSensor = FlameSensor(flame_pin)
        self.gasStandard = 200  # 가스 센서 통해 실험 해보고 값 변경할 것.

    def calc_time(self):
        now = datetime.datetime.now()
        date = now.strftime("%Y/%m/%d %H:%M")
        return date

    def send_message_to_firebase(self):
        date = self.calc_time()

        if self.mq2Sensor.gas() > self.gasStandard:
            print(f'Fire detected on {self.floor} floor')
            Fcm.sendFcm()
#            doc_ref.set({
#                u'Time': date,
#                u'Floor': self.floor,
#                u'FireDetected': u'TRUE'
#            })
#         else:
           # doc_ref.set({
           #     u'Time': date,
           #     u'Floor': self.floor,
           #     u'FireDetected': u'FALSE'
           # })

    def fire_detect(self):
        gpio.add_event_detect(self.flameSensor.pin, gpio.RISING, callback=lambda x: self.send_message_to_firebase(),
                              bouncetime=50)

def add_dict(to_add, floor):
    for num, floors in main.floors_dict.items():
        if (num != floor and to_add in floors):
            floors.remove(to_add)
            main.floors_dict[num] = floors
        elif (num == floor and to_add in floors):
            return
        elif (num == floor and to_add not in floors):
            main.floors_dict[floor].append(to_add)
        db.collection(u'floors').document(str(num)).set({
            'tokens': main.floors_dict[num]
        })


def sendFcm():
    users_ref = db.collection(u'workplace')
    docs = users_ref.stream()
    for doc in docs:
        if ((doc.to_dict())["enter"]):
            print(f'{(doc.to_dict())["token"]} = {(doc.to_dict())["enter"]}')
            # print((doc.to_dict()))
            msg = "your floor is " + str((doc.to_dict())["floor"])
            payload = json.dumps({
                "to": (doc.to_dict())["token"],
                "notification": {
                    "title": "Warning!!!",
                    "body": "Fire in the building!!!!",
                    "image": "https://us.123rf.com/450wm/yehorlisnyi/yehorlisnyi1610/yehorlisnyi161000137/64114511-%EA%B2%A9%EB%A6%AC-%EB%90%9C-%EC%B6%94%EC%83%81-%EB%B6%89%EC%9D%80-%EC%83%89%EA%B3%BC-%EC%98%A4%EB%A0%8C%EC%A7%80%EC%83%89-%ED%99%94%EC%9E%AC-%EB%B6%88%EA%BD%83-%ED%9D%B0%EC%83%89-%EB%B0%B0%EA%B2%BD%EC%97%90-%EC%84%A4%EC%A0%95-%EC%BA%A0%ED%94%84-%ED%8C%8C%EC%9D%B4%EC%96%B4-%EB%A7%A4%EC%9A%B4-%EC%9D%8C%EC%8B%9D-%EA%B8%B0%ED%98%B8%EC%9E%85%EB%8B%88%EB%8B%A4-%EC%97%B4-%EC%95%84%EC%9D%B4%EC%BD%98%EC%9E%85%EB%8B%88%EB%8B%A4-%EB%9C%A8%EA%B1%B0%EC%9A%B4-%EC%97%90%EB%84%88%EC%A7%80-%EA%B8%B0%ED%98%B8%EC%9E%85%EB%8B%88%EB%8B%A4-%EB%B2%A1%ED%84%B0-%ED%99%94%EC%9E%AC-%EA%B7%B8%EB%A6%BC%EC%9E%85%EB%8B%88%EB%8B%A4-.jpg?ver=6"
                },
                "data": {
                    "floor": (doc.to_dict())['floor']
                }
            })
            response = requests.request("POST", url, headers=headers, data=payload)
            print(response.text)
    print(type(docs))


# Create a callback on_snapshot function to capture changes
def on_snapshot(col_snapshot ,changes, read_time):
    print(u'Callback received query snapshot.')
    print(f"floor :")
    for doc in col_snapshot:
        add_dict(doc.id, (doc.to_dict())['floor'])
    callback_done.set()

for i in range(1,3):
    col_query = db.collection(u'workplace').where(u'floor', u'==', i)
    query_watch = col_query.on_snapshot(on_snapshot)
    time.sleep(3)
    db.collection(u'floors').document(str(i)).set({
        'tokens': floors_dict[i]
    })


First_floor = Detect.Floor(1, 17, 0)
Second_floor = Detect.Floor(2, 22, 1)
#Third_floor = Detect.Floor(3, 27, 2)


def process():
    First_floor.fire_detect()
    Second_floor.fire_detect()
    #Third_floor.fire_detect()
    while True:
        time.sleep(3)


if __name__ == '__main__':
    try:
        print("Detect Start")
        process()
    except KeyboardInterrupt:
        print()
        print("End by KeyboardInterrupt!")
        gpio.cleanup()


