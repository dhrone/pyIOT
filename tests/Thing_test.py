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
def ptIOT(request, scope="session"):
    client = boto3.client('iot-data', region_name=REGION)
    return client

def IOTvalue(ptIOT, section, valuedict):
    thingData = json.loads(ptIOT.get_thing_shadow(thingName=THINGNAME)['payload'].read().decode('utf-8'))

    for k in valuedict:
        assert (valuedict[k] == thingData['state'][section].get(k))

def test_Thing_startup(ptThing, ptIOT):
    time.sleep(8)
    preamp = ptThing._components[0]
    preamp.exit()
    IOTvalue(ptIOT, 'reported', { 'powerState': 'ON' })
    time.sleep(2)


def test_Thing_frontPanel(ptThing, ptIOT):
    time.sleep(8)
    preamp = ptThing._components[0]
    preamp._stream.frontPanel('input', 'TV')
    time.sleep(2)
    preamp.exit()

    IOTvalue(ptIOT, 'reported',
        {
            'powerState': 'ON',
            'input': 'TV',
            'volume': 60,
            'muted': False
        }
    )

def test_Thing_fromIOT(ptThing, ptIOT):
    time.sleep(8)
    preamp = ptThing._components[0]
    item = {'state': {'desired': {'input': 'RADIO'}}}
    bdata = json.dumps(item).encode('utf-8')
    response = ptIOT.update_thing_shadow(thingName=THINGNAME, payload = bdata)
    time.sleep(2)

    assert(preamp._stream.properties['input']=='RADIO')
    preamp.exit()
