import pytest
import queue
import time
import json
from threading import Thread
import logging
import sys

import boto3

from tests import example
from tests import simulator

REGION = 'us-east-1'
THINGNAME = 'pyIOTtest'
PATH = 'tests/'

root = logging.getLogger('pyIOT')
root.setLevel(logging.DEBUG)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
root.addHandler(ch)
del root
del ch

root = logging.getLogger('tests')
root.setLevel(logging.INFO)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
root.addHandler(ch)
del root
del ch


@pytest.fixture
def ptThing(request):
    stream = simulator.preampSim()
    preamp = example.preampComponent(name = 'pyIOT_test_preamp', stream = stream)
    Thing = example.TVThing(endpoint='aamloz0nbas89.iot.us-east-1.amazonaws.com', thingName=THINGNAME, rootCAPath=PATH+'root-CA.crt', certificatePath=PATH+THINGNAME+'.crt', privateKeyPath=PATH+THINGNAME+'.private.key', region=REGION, components=preamp)
    Thread(target=Thing.start).start()
    return Thing

@pytest.fixture
def ptIOT(request):
    client = boto3.client('iot-data', region_name=REGION)
    return client

def test_Thing_startup(ptThing, ptIOT):
    time.sleep(15)
    preamp = ptThing._components[0]
    preamp.exit()

    thingData = json.loads(ptIOT.get_thing_shadow(thingName=THINGNAME)['payload'].read().decode('utf-8'))
    reportedState = thingData['state']['reported']
    assert(reportedState['powerState']=='ON')
